"""Sentiment scoring for tickets.

The requester's latest public message is classified as ``positive``, ``neutral``
or ``negative`` by the workspace's configured AI provider. Scoring runs in the
worker (never on the request path) and is a no-op when the workspace has not
configured AI, so ticket creation stays fast and AI-free by default.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ticket, TicketMessage, Workspace
from app.services import ai as ai_service

logger = logging.getLogger(__name__)

LABELS = ("positive", "neutral", "negative")
SYSTEM_PROMPT = (
    "You classify customer support messages. Reply with exactly one word: "
    "positive, neutral or negative. No punctuation, no explanation."
)


def _parse(reply: str) -> str | None:
    lowered = (reply or "").strip().lower()
    for label in LABELS:
        if label in lowered:
            return label
    return None


async def analyze(workspace: Workspace, text: str) -> str | None:
    """Classify one message, or ``None`` when AI is unconfigured or unusable."""
    if not text or not text.strip():
        return None
    try:
        ai_service.require_chat_config(workspace)
    except ai_service.AINotConfiguredError:
        return None
    try:
        result = await ai_service.complete_chat(
            workspace,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text.strip()[:2000]}],
            temperature=0.0,
            max_tokens=4,
        )
    except ai_service.AIError as exc:
        logger.info("sentiment: provider failed (%s)", exc)
        return None
    # ``complete_chat`` returns {"content", "provider", "model", "usage"}.
    return _parse((result or {}).get("content") or "")


async def score_pending(db: AsyncSession, *, limit: int = 20) -> int:
    """Score tickets that have no sentiment yet. Returns the count scored."""
    rows = (
        await db.execute(
            select(Ticket, Workspace)
            .join(Workspace, Workspace.id == Ticket.workspace_id)
            .where(Ticket.sentiment.is_(None))
            .order_by(Ticket.created_at.desc())
            .limit(max(1, limit))
        )
    ).all()
    scored = 0
    for ticket, workspace in rows:
        message = (
            await db.execute(
                select(TicketMessage.body)
                .where(
                    TicketMessage.ticket_id == ticket.id,
                    TicketMessage.author_type == "requester",
                    TicketMessage.visibility == "public",
                )
                .order_by(TicketMessage.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        label = await analyze(workspace, message or ticket.subject)
        if label is None:
            # Leave it unscored so a later tick can retry (e.g. AI not configured).
            continue
        ticket.sentiment = label
        scored += 1
    if scored:
        await db.commit()
    return scored
