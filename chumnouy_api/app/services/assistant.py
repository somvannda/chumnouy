"""Support assistant grounded in the workspace knowledge corpus.

Answers are retrieved from the workspace's active articles (a keyword score over
title/summary/body, filtered by locale and optional vertical/role) so the model
does not invent features or steps. Provider selection, keys and errors are
reused from ``app.services.ai``. Generalized from Chmaba POS
``services/support.py`` (company corpus → workspace corpus).
"""
from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.deps import TenantContext
from app.models import (
    AssistantConversation,
    AssistantFeedback,
    AssistantMessage,
    KnowledgeArticle,
    Ticket,
    TicketMessage,
    Workspace,
    utcnow,
)
from app.schemas import AssistantFeedbackCreate
from app.services import ai as ai_service

MAX_ARTICLES = 6
MAX_TURN_CHARS = 2000
CONVERSATION_TITLE_CHARS = 80

SYSTEM_PROMPT = (
    "You are Chumnouy's support assistant, helping a support team answer "
    "questions about the product.\n"
    "Rules:\n"
    "- Answer only from the GUIDES below. Never invent features, prices, menu "
    "locations or steps.\n"
    "- If the guides do not cover the question, say so and suggest a human agent "
    "or opening a ticket.\n"
    "- Be concise and concrete. Prefer short numbered steps.\n"
    "- Never ask for passwords, card numbers or other secrets."
)

AGENT_DRAFT_SYSTEM = (
    "You are a customer-support agent. Turn the conversation into the reply a "
    "customer should receive.\n"
    "Rules:\n"
    "- Write warm, clear, professional prose the customer can act on.\n"
    "- Keep it concise; prefer short paragraphs or numbered steps.\n"
    "- Never invent features, prices, policies or timelines not present in the "
    "conversation or instructions.\n"
    "- Do not mention that a machine wrote this, and return plain text only."
)

# In-process sliding-window limiter. A single API process today; move to shared
# storage if the API scales to multiple workers (docs/architecture.md).
_rate_windows: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str, *, limit: int, window_seconds: int = 3600) -> bool:
    """True and record the call when under the limit, else False (<=0 disables)."""
    if limit <= 0:
        return True
    now = time.monotonic()
    window = _rate_windows[key]
    while window and now - window[0] > window_seconds:
        window.popleft()
    if len(window) >= limit:
        return False
    window.append(now)
    return True


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def _article_haystack(article: KnowledgeArticle) -> str:
    return f"{article.title} {article.summary or ''} {article.body}"


def retrieve(
    articles: list[KnowledgeArticle],
    *,
    question: str,
    locale: str | None,
    vertical: str | None,
    role: str | None,
    limit: int = MAX_ARTICLES,
) -> tuple[list[KnowledgeArticle], bool]:
    """Return ``(selected, matched)`` articles for a question.

    Filtering is by locale and (when the article targets one) vertical/role, so a
    workspace is only ever grounded in guidance meant for it.
    """
    query = _tokens(question)
    scored: list[tuple[int, KnowledgeArticle]] = []
    for article in articles:
        if locale and article.locale != locale:
            continue
        if article.verticals and vertical and vertical not in article.verticals:
            continue
        if article.roles and role and role not in article.roles:
            continue
        score = len(query & _tokens(_article_haystack(article)))
        scored.append((score, article))
    scored.sort(key=lambda pair: (-pair[0], pair[1].position, pair[1].created_at))
    matched = [article for score, article in scored if score > 0]
    selected = matched[:limit] or [article for _score, article in scored[:limit]]
    return selected, bool(matched)


def _clamp_history(history: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for turn in (history or [])[-settings.assistant_max_history_turns:]:
        content = str(turn.get("content") or "").strip()
        if not content:
            continue
        cleaned.append(
            {
                "role": "assistant" if turn.get("role") == "assistant" else "user",
                "content": content[:MAX_TURN_CHARS],
            }
        )
    return cleaned


def build_prompt(
    *,
    question: str,
    history: list[dict[str, Any]] | None,
    locale: str,
    context: dict[str, Any] | None,
    articles: list[KnowledgeArticle],
) -> tuple[str, list[dict[str, str]], list[KnowledgeArticle]]:
    """Return ``(system, messages, citations)`` for a grounded question."""
    cleaned = (question or "").strip()[: settings.assistant_max_question_chars]
    if not cleaned:
        raise ValueError("Ask a question to get started.")
    context = context or {}
    vertical = context.get("vertical")
    role = context.get("role")
    selected, matched = retrieve(
        articles, question=cleaned, locale=locale, vertical=vertical, role=role
    )
    guides = "\n\n".join(f"### {a.title}\n{a.body}" for a in selected) or "(no matching guides)"
    language = (
        "\n\nReply in Khmer (ភាសាខ្មែរ), in a natural, helpful tone. Keep menu and "
        "button names exactly as they appear in the app."
        if locale == "km"
        else ""
    )
    match_note = (
        ""
        if matched
        else "\n\nNOTE: no guide matched this question exactly. If none of the guides "
        "answers it, say you are not sure and suggest opening a ticket — do not guess."
    )
    system = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Business type: {vertical or 'general'}. Role: {role or 'agent'}.\n\n"
        f"GUIDES:\n{guides}{language}{match_note}"
    )
    messages = [*_clamp_history(history), {"role": "user", "content": cleaned}]
    return system, messages, selected


async def load_corpus(db: AsyncSession, workspace_id: UUID) -> list[KnowledgeArticle]:
    rows = (
        await db.execute(
            select(KnowledgeArticle)
            .where(
                KnowledgeArticle.workspace_id == workspace_id,
                KnowledgeArticle.is_active.is_(True),
            )
            .order_by(KnowledgeArticle.position, KnowledgeArticle.created_at)
        )
    ).scalars().all()
    return list(rows)


def _title_from(question: str) -> str:
    text = " ".join((question or "").split())
    if not text:
        return "New chat"
    return text[:CONVERSATION_TITLE_CHARS] + ("…" if len(text) > CONVERSATION_TITLE_CHARS else "")


async def resolve_conversation(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    conversation_id: UUID | None,
    question: str,
    locale: str,
) -> AssistantConversation:
    """Return the caller's conversation, creating one only on first use.

    Scoped to the workspace and the acting user (or integration), so a workspace
    can never read or append to another's.
    """
    owner = AssistantConversation.user_id == ctx.user.id if ctx.user else (
        AssistantConversation.integration_id == (ctx.integration.id if ctx.integration else None)
    )
    if conversation_id is not None:
        row = (
            await db.execute(
                select(AssistantConversation).where(
                    AssistantConversation.id == conversation_id,
                    AssistantConversation.workspace_id == ctx.workspace.id,
                    owner,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise LookupError("Conversation not found")
        return row
    row = (
        await db.execute(
            select(AssistantConversation)
            .where(AssistantConversation.workspace_id == ctx.workspace.id, owner)
            .order_by(AssistantConversation.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        row = AssistantConversation(
            workspace_id=ctx.workspace.id,
            user_id=ctx.user.id if ctx.user else None,
            integration_id=ctx.integration.id if ctx.integration else None,
            title=_title_from(question),
            locale=locale,
        )
        db.add(row)
        await db.flush()
    return row


async def add_message(
    db: AsyncSession,
    conversation: AssistantConversation,
    *,
    role: str,
    content: str,
    citations: list[dict] | None = None,
    usage: dict | None = None,
) -> AssistantMessage:
    message = AssistantMessage(
        conversation_id=conversation.id,
        workspace_id=conversation.workspace_id,
        role=role,
        content=content,
        citations=citations or [],
        usage=usage or {},
    )
    db.add(message)
    conversation.updated_at = utcnow()
    await db.flush()
    return message


async def persist_message_standalone(
    *,
    conversation_id: UUID,
    role: str,
    content: str,
    citations: list[dict] | None = None,
    usage: dict | None = None,
) -> UUID:
    """Persist a message on its own session (used after a stream completes)."""
    async with SessionLocal() as session:
        conversation = await session.get(AssistantConversation, conversation_id)
        if conversation is None:
            raise LookupError("Conversation not found")
        message = await add_message(
            session, conversation, role=role, content=content, citations=citations, usage=usage
        )
        await session.commit()
        return message.id


def citation_payload(articles: list[KnowledgeArticle]) -> list[dict]:
    return [
        {"id": str(article.id), "title": article.title, "slug": article.slug}
        for article in articles
    ]


async def list_conversations(
    db: AsyncSession, ctx: TenantContext, *, limit: int = 50
) -> list[AssistantConversation]:
    owner = AssistantConversation.user_id == ctx.user.id if ctx.user else (
        AssistantConversation.integration_id == (ctx.integration.id if ctx.integration else None)
    )
    rows = (
        await db.execute(
            select(AssistantConversation)
            .where(AssistantConversation.workspace_id == ctx.workspace.id, owner)
            .order_by(AssistantConversation.updated_at.desc())
            .limit(max(1, min(limit, 200)))
        )
    ).scalars().all()
    return list(rows)


async def conversation_detail(
    db: AsyncSession, ctx: TenantContext, conversation_id: UUID
) -> tuple[AssistantConversation, list[AssistantMessage]] | None:
    owner = AssistantConversation.user_id == ctx.user.id if ctx.user else (
        AssistantConversation.integration_id == (ctx.integration.id if ctx.integration else None)
    )
    conversation = (
        await db.execute(
            select(AssistantConversation).where(
                AssistantConversation.id == conversation_id,
                AssistantConversation.workspace_id == ctx.workspace.id,
                owner,
            )
        )
    ).scalar_one_or_none()
    if conversation is None:
        return None
    messages = (
        await db.execute(
            select(AssistantMessage)
            .where(AssistantMessage.conversation_id == conversation_id)
            .order_by(AssistantMessage.created_at)
        )
    ).scalars().all()
    return conversation, list(messages)


async def record_feedback(
    db: AsyncSession, ctx: TenantContext, payload: AssistantFeedbackCreate
) -> AssistantFeedback:
    message = (
        await db.execute(
            select(AssistantMessage).where(
                AssistantMessage.id == payload.message_id,
                AssistantMessage.workspace_id == ctx.workspace.id,
            )
        )
    ).scalar_one_or_none()
    if message is None:
        raise LookupError("Message not found")
    feedback = AssistantFeedback(
        workspace_id=ctx.workspace.id,
        message_id=message.id,
        rating=payload.rating,
        comment=payload.comment,
        created_by=ctx.user.id if ctx.user else None,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return feedback


async def draft_reply(
    workspace: Workspace,
    *,
    ticket: Ticket,
    messages: list[TicketMessage],
    instruction: str | None = None,
    tone: str | None = None,
) -> dict:
    """Draft an agent reply from a ticket thread (reuses the provider plumbing)."""
    conversation = "\n".join(f"{m.author_type}: {m.body}" for m in messages) or "(no messages)"
    lines = [
        f"Support ticket: {ticket.subject}",
        f"Conversation:\n{conversation}",
    ]
    if instruction:
        lines.append(f"Instructions: {instruction.strip()}")
    if tone:
        lines.append(f"Tone: {tone.strip()}")
    lines.append("Write the reply to send to the customer.")
    result = await ai_service.complete_chat(
        workspace,
        system=AGENT_DRAFT_SYSTEM,
        messages=[{"role": "user", "content": "\n\n".join(lines)}],
        temperature=0.4,
        max_tokens=settings.assistant_max_output_tokens,
    )
    return {
        "draft": (result.get("content") or "").strip(),
        "provider": result.get("provider"),
        "model": result.get("model"),
    }


async def stream_answer(
    workspace: Workspace,
    *,
    system: str,
    messages: list[dict[str, str]],
    usage_out: dict | None = None,
) -> AsyncIterator[str]:
    async for chunk in ai_service.stream_chat(
        workspace,
        system=system,
        messages=messages,
        temperature=0.3,
        max_tokens=settings.assistant_max_output_tokens,
        usage_out=usage_out,
    ):
        yield chunk
