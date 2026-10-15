"""Live chat — agent side (console)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import WorkspaceContext, get_workspace_context
from app.schemas import ChatMessageCreate, ChatMessageRead, ChatSessionDetail, ChatSessionRead
from app.services import chat as svc

router = APIRouter(prefix="/console/chat", tags=["chat"])


async def _session(db: AsyncSession, ctx: WorkspaceContext, session_id: UUID):
    session = await svc.load_session(db, ctx.workspace.id, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
    return session


@router.get("/sessions", response_model=list[ChatSessionRead])
async def list_sessions(
    status_filter: str | None = None,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[ChatSessionRead]:
    return await svc.list_sessions(db, ctx.workspace.id, status=status_filter)


@router.get("/sessions/{session_id}", response_model=ChatSessionDetail)
async def get_session(
    session_id: UUID,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionDetail:
    return await svc.session_detail(db, await _session(db, ctx, session_id))


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatMessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def reply(
    session_id: UUID,
    payload: ChatMessageCreate,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageRead:
    session = await _session(db, ctx, session_id)
    return await svc.add_message(
        db, session, author_type="agent", author_user_id=ctx.user.id, body=payload.body
    )


@router.post("/sessions/{session_id}/close", response_model=ChatSessionRead)
async def close(
    session_id: UUID,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionRead:
    return await svc.close_session(db, await _session(db, ctx, session_id))
