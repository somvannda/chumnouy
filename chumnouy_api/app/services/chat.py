"""Live chat: sessions and messages.

Polling v1 (the client re-fetches the session); an SSE/WebSocket transport can be
added later without changing the model. Requesters reach a session with their
portal token; agents through the console.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, ChatSession, Requester, Workspace, utcnow
from app.schemas import ChatMessageRead, ChatSessionDetail, ChatSessionRead
from app.services import notifyr as notifyr_svc


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
    if author_type == "agent":
        # Delivery is Notifyr's job; we only queue the hand-off (no-op when the
        # workspace has not configured Notifyr).
        await _enqueue_reply_nudge(db, session, body)
    await db.commit()
    await db.refresh(message)
    return _message_read(message)


async def _enqueue_reply_nudge(db: AsyncSession, session: ChatSession, body: str) -> None:
    """Queue a Notifyr hand-off so the requester hears about an agent reply."""
    workspace = await db.get(Workspace, session.workspace_id)
    if workspace is None or session.requester_id is None:
        return
    requester = await db.get(Requester, session.requester_id)
    if requester is None or not requester.email:
        return
    await notifyr_svc.enqueue_chat(
        db,
        workspace=workspace,
        session=session,
        recipient=requester.email,
        variables={"message": body[:280]},
    )


def _aware(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat them as UTC so comparisons work."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


async def messages_after(
    db: AsyncSession, session: ChatSession, cursor: datetime
) -> list[ChatMessage]:
    """Messages created at or after ``cursor`` (callers de-duplicate by id)."""
    return (
        await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id, ChatMessage.created_at >= cursor)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        )
    ).scalars().all()


async def stream_events(
    db: AsyncSession,
    session: ChatSession,
    *,
    after: datetime | None = None,
    timeout: float = 25.0,
    interval: float = 1.0,
) -> AsyncIterator[tuple[str, dict]]:
    """Yield ``(event, data)`` pairs for one chat session.

    Emits ``ready`` once, then a ``message`` event per new message, then ``done``
    when the bounded window closes (the client reconnects). ``after`` catches the
    client up on messages it has not seen yet.
    """
    deadline = time.monotonic() + timeout
    cursor = after or session.created_at
    seen: set[UUID] = set()
    yield "ready", {"session_id": str(session.id), "status": session.status}
    while True:
        for message in await messages_after(db, session, cursor):
            if message.id in seen:
                continue
            seen.add(message.id)
            if _aware(message.created_at) > _aware(cursor):
                cursor = message.created_at
            yield "message", _message_read(message).model_dump(mode="json")
        if time.monotonic() >= deadline:
            yield "done", {"session_id": str(session.id)}
            return
        await asyncio.sleep(interval)
        # End the read transaction so messages committed by other sessions show up.
        await db.commit()


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
