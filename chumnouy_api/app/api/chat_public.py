"""Live chat — requester side (portal token)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.chat_stream import stream_response
from app.db import get_db
from app.deps import RequesterContext, get_requester_context
from app.schemas import ChatMessageCreate, ChatMessageRead, ChatSessionDetail, ChatSessionRead
from app.services import chat as svc

router = APIRouter(prefix="/public/chat", tags=["chat"])

_requester = get_requester_context


async def _session(db: AsyncSession, ctx: RequesterContext, session_id: UUID):
    session = await svc.load_session(db, ctx.workspace.id, session_id)
    if session is None or session.requester_id != ctx.requester.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
    return session


@router.post("/sessions", response_model=ChatSessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    ctx: RequesterContext = Depends(_requester),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionRead:
    return await svc.create_session(db, ctx.workspace, ctx.requester)


@router.get("/sessions/{session_id}", response_model=ChatSessionDetail)
async def get_session(
    session_id: UUID,
    ctx: RequesterContext = Depends(_requester),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionDetail:
    return await svc.session_detail(db, await _session(db, ctx, session_id))


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatMessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    session_id: UUID,
    payload: ChatMessageCreate,
    ctx: RequesterContext = Depends(_requester),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageRead:
    session = await _session(db, ctx, session_id)
    if session.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Chat session is closed")
    return await svc.add_message(db, session, author_type="requester", author_user_id=None, body=payload.body)


@router.get("/sessions/{session_id}/stream")
async def stream_session(
    session_id: UUID,
    after: datetime | None = None,
    timeout: float = 25.0,
    ctx: RequesterContext = Depends(_requester),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE: agent replies in my session (bounded; the client reconnects)."""
    session = await _session(db, ctx, session_id)
    return stream_response(db, session, after=after, timeout=timeout)
