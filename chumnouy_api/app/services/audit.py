"""Workspace audit log: a read view over ticket events.

Every ticket write already records a ``ticket_events`` row (created, replied,
updated, resolved, assigned, …). This exposes them as a filterable audit trail.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TicketEvent, WorkspaceEvent
from app.schemas import AuditEventRead, AuditListRead, WorkspaceEventListRead, WorkspaceEventRead


def _read(event: TicketEvent) -> AuditEventRead:
    return AuditEventRead(
        id=event.id,
        ticket_id=event.ticket_id,
        type=event.type,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        data=dict(event.data or {}),
        created_at=event.created_at,
    )


async def list_events(
    db: AsyncSession,
    workspace_id: UUID,
    *,
    type: str | None = None,
    actor_type: str | None = None,
    ticket_id: UUID | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> AuditListRead:
    stmt = select(TicketEvent).where(TicketEvent.workspace_id == workspace_id)
    if type:
        stmt = stmt.where(TicketEvent.type == type)
    if actor_type:
        stmt = stmt.where(TicketEvent.actor_type == actor_type)
    if ticket_id is not None:
        stmt = stmt.where(TicketEvent.ticket_id == ticket_id)
    stmt = stmt.order_by(TicketEvent.created_at.desc(), TicketEvent.id.desc())

    offset = int(cursor) if cursor else 0
    capped = max(1, min(limit, 200))
    rows = (await db.execute(stmt.offset(offset).limit(capped + 1))).scalars().all()
    has_more = len(rows) > capped
    rows = rows[:capped]
    return AuditListRead(
        data=[_read(event) for event in rows],
        next_cursor=str(offset + capped) if has_more else None,
    )


# --- Account/workspace-level events -------------------------------------------
# Ticket writes already record ``ticket_events``; settings, member and key
# changes record here so the audit trail covers the account too.


def record_workspace_event(
    db: AsyncSession,
    workspace_id: UUID,
    *,
    type: str,
    actor_type: str = "user",
    actor_id: UUID | None = None,
    data: dict | None = None,
) -> WorkspaceEvent:
    """Stage an audit event in the caller's transaction (no commit)."""
    event = WorkspaceEvent(
        workspace_id=workspace_id,
        type=type,
        actor_type=actor_type,
        actor_id=actor_id,
        data=data or {},
    )
    db.add(event)
    return event


def _workspace_read(event: WorkspaceEvent) -> WorkspaceEventRead:
    return WorkspaceEventRead(
        id=event.id,
        type=event.type,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        data=dict(event.data or {}),
        created_at=event.created_at,
    )


async def list_workspace_events(
    db: AsyncSession,
    workspace_id: UUID,
    *,
    type: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> WorkspaceEventListRead:
    stmt = select(WorkspaceEvent).where(WorkspaceEvent.workspace_id == workspace_id)
    if type:
        stmt = stmt.where(WorkspaceEvent.type == type)
    stmt = stmt.order_by(WorkspaceEvent.created_at.desc(), WorkspaceEvent.id.desc())

    offset = int(cursor) if cursor else 0
    capped = max(1, min(limit, 200))
    rows = (await db.execute(stmt.offset(offset).limit(capped + 1))).scalars().all()
    has_more = len(rows) > capped
    rows = rows[:capped]
    return WorkspaceEventListRead(
        data=[_workspace_read(event) for event in rows],
        next_cursor=str(offset + capped) if has_more else None,
    )
