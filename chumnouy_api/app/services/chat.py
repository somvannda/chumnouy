"""Live chat: sessions and messages.

Polling v1 (the client re-fetches the session); an SSE/WebSocket transport can be
added later without changing the model. Requesters reach a session with their
portal token; agents through the console.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, ChatSession, Requester, Workspace, utcnow
from app.schemas import ChatMessageRead, ChatSessionDetail, ChatSessionRead


def _message_read(message: ChatMessage) -> ChatMessageRead:
    return ChatMessageRead(
        id=message.id,
        author_type=message.author_type,
        body=message.body,
        created_at=message.created_at,
    )


def _session_read(session: ChatSession) -> ChatSessionRead:
    return ChatSessionRead(
        id=session.id,
        status=session.status,
        created_at=session.created_at,
        closed_at=session.closed_at,
    )


async def create_session(
    db: AsyncSession, workspace: Workspace, requester: Requester
) -> ChatSessionRead:
    session = ChatSession(workspace_id=workspace.id, requester_id=requester.id, status="open")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_read(session)


async def load_session(
    db: AsyncSession, workspace_id: UUID, session_id: UUID
) -> ChatSession | None:
    return (
        await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id, ChatSession.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()


async def session_detail(db: AsyncSession, session: ChatSession) -> ChatSessionDetail:
    messages = (
        await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at)
        )
    ).scalars().all()
    base = _session_read(session)
    return ChatSessionDetail(
        **base.model_dump(), messages=[_message_read(m) for m in messages]
    )


async def add_message(
    db: AsyncSession,
    session: ChatSession,
    *,
    author_type: str,
    author_user_id: UUID | None,
    body: str,
) -> ChatMessageRead:
    message = ChatMessage(
        session_id=session.id,
        workspace_id=session.workspace_id,
        author_type=author_type,
        author_user_id=author_user_id,
        body=body,
    )
    db.add(message)
    session.updated_at = utcnow()
    await db.commit()
    await db.refresh(message)
    return _message_read(message)


async def list_sessions(
    db: AsyncSession, workspace_id: UUID, *, status: str | None = None, limit: int = 50
) -> list[ChatSessionRead]:
    stmt = select(ChatSession).where(ChatSession.workspace_id == workspace_id)
    if status:
        stmt = stmt.where(ChatSession.status == status)
    stmt = stmt.order_by(ChatSession.updated_at.desc()).limit(max(1, min(limit, 200)))
    rows = (await db.execute(stmt)).scalars().all()
    return [_session_read(row) for row in rows]


async def close_session(db: AsyncSession, session: ChatSession) -> ChatSessionRead:
    session.status = "closed"
    session.closed_at = utcnow()
    await db.commit()
    await db.refresh(session)
    return _session_read(session)
