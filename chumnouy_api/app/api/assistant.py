"""AI assistant (v1).

Grounded answers stream from ``POST /assistant/chat`` (SSE). Conversations are
persisted per caller; answers can be rated; agents can draft a reply on a ticket.
All endpoints need the ``assistant:use`` scope.
"""
from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.models import Ticket, TicketMessage
from app.schemas import (
    AgentDraftRead,
    AgentDraftRequest,
    AssistantChatRequest,
    AssistantConversationDetail,
    AssistantConversationRead,
    AssistantFeedbackCreate,
    AssistantFeedbackRead,
    AssistantMessageRead,
    AssistantSummaryRead,
    AssistantTriageRead,
)
from app.services import ai as ai_service
from app.services import assistant as svc
from app.services import tickets as tickets_svc

router = APIRouter(tags=["assistant"])

_use = require_tenant_scopes("assistant:use")

SSE_MEDIA_TYPE = "text/event-stream"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post("/assistant/chat")
async def chat(
    payload: AssistantChatRequest,
    ctx: TenantContext = Depends(_use),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    if not svc.check_rate_limit(
        f"assistant:{ctx.workspace.id}", limit=settings.assistant_rate_limit_per_hour
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many assistant requests; try again later",
        )
    # Fail before the stream starts so a setup problem is a normal 400.
    try:
        ai_service.require_chat_config(ctx.workspace)
    except ai_service.AINotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    articles = await svc.load_corpus(db, ctx.workspace.id)
    try:
        system, messages, citations = svc.build_prompt(
            question=payload.question,
            history=payload.history,
            locale=payload.locale,
            context=payload.context,
            articles=articles,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    try:
        conversation = await svc.resolve_conversation(
            db, ctx, conversation_id=payload.conversation_id, question=payload.question, locale=payload.locale
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    await svc.add_message(db, conversation, role="user", content=payload.question.strip())
    await db.commit()

    workspace = ctx.workspace
    conversation_id = conversation.id
    citation_data = svc.citation_payload(citations)

    async def event_stream():
        yield _sse("citation", {"citations": citation_data})
        usage: dict = {}
        collected: list[str] = []
        try:
            async for chunk in svc.stream_answer(
                workspace, system=system, messages=messages, usage_out=usage
            ):
                collected.append(chunk)
                yield _sse("token", {"text": chunk})
        except ai_service.AIError as exc:
            yield _sse("error", {"message": str(exc)})
            return
        content = "".join(collected)
        try:
            message_id = await svc.persist_message_standalone(
                conversation_id=conversation_id,
                role="assistant",
                content=content,
                citations=citation_data,
                usage=usage,
            )
        except LookupError:
            message_id = None
        yield _sse(
            "done",
            {
                "conversation_id": str(conversation_id),
                "message_id": str(message_id) if message_id else None,
                "citations": citation_data,
            },
        )

    return StreamingResponse(event_stream(), media_type=SSE_MEDIA_TYPE)


def _conversation_read(conversation) -> AssistantConversationRead:
    return AssistantConversationRead(
        id=conversation.id,
        title=conversation.title,
        locale=conversation.locale,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.get("/assistant/conversations", response_model=list[AssistantConversationRead])
async def list_conversations(
    ctx: TenantContext = Depends(_use),
    db: AsyncSession = Depends(get_db),
) -> list[AssistantConversationRead]:
    rows = await svc.list_conversations(db, ctx)
    return [_conversation_read(conversation) for conversation in rows]


@router.get("/assistant/conversations/{conversation_id}", response_model=AssistantConversationDetail)
async def conversation_detail(
    conversation_id: UUID,
    ctx: TenantContext = Depends(_use),
    db: AsyncSession = Depends(get_db),
) -> AssistantConversationDetail:
    result = await svc.conversation_detail(db, ctx, conversation_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    conversation, messages = result
    base = _conversation_read(conversation)
    return AssistantConversationDetail(
        **base.model_dump(),
        messages=[
            AssistantMessageRead(
                id=message.id,
                role=message.role,
                content=message.content,
                citations=list(message.citations or []),
                created_at=message.created_at,
            )
            for message in messages
        ],
    )


@router.post(
    "/assistant/feedback",
    response_model=AssistantFeedbackRead,
    status_code=status.HTTP_201_CREATED,
)
async def feedback(
    payload: AssistantFeedbackCreate,
    ctx: TenantContext = Depends(_use),
    db: AsyncSession = Depends(get_db),
) -> AssistantFeedbackRead:
    try:
        row = await svc.record_feedback(db, ctx, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return AssistantFeedbackRead(
        id=row.id,
        message_id=row.message_id,
        rating=row.rating,
        comment=row.comment,
        created_at=row.created_at,
    )


@router.post("/tickets/{ticket_id}/assistant/draft", response_model=AgentDraftRead)
async def draft_reply(
    ticket_id: UUID,
    payload: AgentDraftRequest,
    ctx: TenantContext = Depends(_use),
    db: AsyncSession = Depends(get_db),
) -> AgentDraftRead:
    ticket = await tickets_svc.load_ticket(db, ctx.workspace.id, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    messages = (
        await db.execute(
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.created_at)
        )
    ).scalars().all()
    try:
        result = await svc.draft_reply(
            ctx.workspace,
            ticket=ticket,
            messages=list(messages),
            instruction=payload.instruction,
            tone=payload.tone,
        )
    except ai_service.AINotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ai_service.AIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return AgentDraftRead(**result)


async def _thread(db: AsyncSession, workspace_id, ticket_id: UUID) -> tuple[Ticket, list[TicketMessage]]:
    ticket = await tickets_svc.load_ticket(db, workspace_id, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    messages = (
        await db.execute(
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.created_at)
        )
    ).scalars().all()
    return ticket, list(messages)


@router.post("/tickets/{ticket_id}/assistant/summary", response_model=AssistantSummaryRead)
async def summarize_ticket(
    ticket_id: UUID,
    ctx: TenantContext = Depends(_use),
    db: AsyncSession = Depends(get_db),
) -> AssistantSummaryRead:
    ticket, messages = await _thread(db, ctx.workspace.id, ticket_id)
    try:
        result = await svc.summarize_thread(ctx.workspace, ticket=ticket, messages=messages)
    except ai_service.AINotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ai_service.AIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return AssistantSummaryRead(**result)


@router.post("/tickets/{ticket_id}/assistant/triage", response_model=AssistantTriageRead)
async def triage_ticket(
    ticket_id: UUID,
    ctx: TenantContext = Depends(_use),
    db: AsyncSession = Depends(get_db),
) -> AssistantTriageRead:
    ticket, messages = await _thread(db, ctx.workspace.id, ticket_id)
    try:
        result = await svc.suggest_triage(ctx.workspace, ticket=ticket, messages=messages)
    except ai_service.AINotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ai_service.AIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return AssistantTriageRead(**result)
