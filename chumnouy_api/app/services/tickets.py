"""Ticket domain logic.

All functions take a ``workspace_id`` and never read it from the request body, so
callers cannot reach another workspace (docs/tenancy.md). Read models are built
explicitly because the ORM attribute for the JSON column is ``metadata_json``.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import TenantContext
from app.models import Requester, Ticket, TicketEvent, TicketMessage, utcnow
from app.schemas import (
    AttachmentRead,
    RequesterInput,
    RequesterRead,
    TicketCreate,
    TicketDetailRead,
    TicketListRead,
    TicketMessageCreate,
    TicketMessageRead,
    TicketRead,
    TicketUpdate,
)
from app.services import attachments as attachments_svc
from app.services import notifyr as notifyr_svc
from app.services import webhooks as webhooks_svc

REFERENCE_PREFIX = "CMY"
OPEN_STATUSES = ("open", "pending")


def _requester_read(requester: Requester | None) -> RequesterRead | None:
    if requester is None:
        return None
    return RequesterRead(
        id=requester.id,
        external_id=requester.external_id,
        name=requester.name,
        email=requester.email,
        phone=requester.phone,
        metadata=requester.metadata_json or {},
    )


def ticket_read(ticket: Ticket, requester: Requester | None) -> TicketRead:
    return TicketRead(
        id=ticket.id,
        reference=ticket.reference,
        subject=ticket.subject,
        status=ticket.status,
        priority=ticket.priority,
        assignee_user_id=ticket.assignee_user_id,
        requester=_requester_read(requester),
        tags=list(ticket.tags or []),
        metadata=dict(ticket.metadata_json or {}),
        created_at=ticket.created_at,
        resolved_at=ticket.resolved_at,
    )


def message_read(
    message: TicketMessage, attachments: list[AttachmentRead] | None = None
) -> TicketMessageRead:
    return TicketMessageRead(
        id=message.id,
        author_type=message.author_type,
        visibility=message.visibility,
        body=message.body,
        created_at=message.created_at,
        attachments=attachments or [],
    )


async def record_event(
    db: AsyncSession,
    *,
    ticket: Ticket,
    type: str,
    actor_type: str,
    actor_id: UUID | None = None,
    data: dict | None = None,
) -> None:
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            workspace_id=ticket.workspace_id,
            type=type,
            actor_type=actor_type,
            actor_id=actor_id,
            data=data or {},
        )
    )


async def upsert_requester(
    db: AsyncSession, workspace_id: UUID, payload: RequesterInput
) -> Requester:
    requester = (
        await db.execute(
            select(Requester).where(
                Requester.workspace_id == workspace_id,
                Requester.external_id == payload.external_id,
            )
        )
    ).scalar_one_or_none()
    if requester is None:
        requester = Requester(
            workspace_id=workspace_id,
            external_id=payload.external_id,
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            metadata_json=payload.metadata,
        )
        db.add(requester)
    else:
        # Refresh the profile from the latest input without clearing known fields.
        if payload.name is not None:
            requester.name = payload.name
        if payload.email is not None:
            requester.email = payload.email
        if payload.phone is not None:
            requester.phone = payload.phone
        if payload.metadata:
            merged = dict(requester.metadata_json or {})
            merged.update(payload.metadata)
            requester.metadata_json = merged
    return requester


async def next_reference(db: AsyncSession, workspace_id: UUID) -> tuple[int, str]:
    current = (
        await db.execute(select(func.max(Ticket.number)).where(Ticket.workspace_id == workspace_id))
    ).scalar()
    number = int(current or 0) + 1
    return number, f"{REFERENCE_PREFIX}-{number}"


async def create_ticket(db: AsyncSession, ctx: TenantContext, payload: TicketCreate) -> TicketDetailRead:
    requester = await upsert_requester(db, ctx.workspace.id, payload.requester)
    await db.flush()
    number, reference = await next_reference(db, ctx.workspace.id)
    ticket = Ticket(
        workspace_id=ctx.workspace.id,
        number=number,
        reference=reference,
        subject=payload.subject.strip(),
        status="open",
        priority=payload.priority,
        requester_id=requester.id,
        source_integration_id=ctx.integration.id if ctx.integration else None,
        tags=payload.tags,
        metadata_json=payload.metadata,
    )
    db.add(ticket)
    await db.flush()
    message = TicketMessage(
        ticket_id=ticket.id,
        workspace_id=ticket.workspace_id,
        author_type="requester",
        visibility="public",
        body=payload.message,
    )
    db.add(message)
    try:
        await attachments_svc.bind_attachments(
            db,
            workspace_id=ctx.workspace.id,
            ticket_id=ticket.id,
            message_id=None,
            attachment_ids=payload.attachment_ids,
        )
    except ValueError:
        await db.rollback()
        raise
    await record_event(
        db,
        ticket=ticket,
        type="ticket.created",
        actor_type=ctx.actor_type,
        actor_id=ctx.integration.id if ctx.integration else None,
    )
    await webhooks_svc.enqueue_event(
        db, ticket=ticket, event="ticket.created", data={"reference": ticket.reference}
    )
    await db.commit()
    await db.refresh(ticket)
    # Hand off to Notifyr for human delivery (new ticket → the workspace's agents).
    await notifyr_svc.notify_ticket_event(
        db,
        workspace=ctx.workspace,
        ticket=ticket,
        event=notifyr_svc.TICKET_CREATED,
        variables={"reference": ticket.reference},
    )
    grouped = attachments_svc.group_by_message(await attachments_svc.load_attachments(db, ticket.id))
    return TicketDetailRead(
        **ticket_read(ticket, requester).model_dump(),
        messages=[message_read(message, grouped.get(message.id, []))],
        attachments=grouped.get(None, []),
    )


async def load_ticket(db: AsyncSession, workspace_id: UUID, ticket_id: UUID) -> Ticket | None:
    return (
        await db.execute(
            select(Ticket).where(Ticket.id == ticket_id, Ticket.workspace_id == workspace_id)
        )
    ).scalar_one_or_none()


async def _requester_for(db: AsyncSession, ticket: Ticket) -> Requester | None:
    if ticket.requester_id is None:
        return None
    return (
        await db.execute(select(Requester).where(Requester.id == ticket.requester_id))
    ).scalar_one_or_none()


async def ticket_detail(db: AsyncSession, ticket: Ticket) -> TicketDetailRead:
    requester = await _requester_for(db, ticket)
    messages = (
        await db.execute(
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket.id)
            .order_by(TicketMessage.created_at)
        )
    ).scalars().all()
    grouped = attachments_svc.group_by_message(await attachments_svc.load_attachments(db, ticket.id))
    return TicketDetailRead(
        **ticket_read(ticket, requester).model_dump(),
        messages=[message_read(m, grouped.get(m.id, [])) for m in messages],
        attachments=grouped.get(None, []),
    )


async def list_tickets(
    db: AsyncSession,
    workspace_id: UUID,
    *,
    status: str | None = None,
    priority: str | None = None,
    assignee: str | None = None,
    integration_id: UUID | None = None,
    q: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> TicketListRead:
    stmt = select(Ticket).where(Ticket.workspace_id == workspace_id)
    if status:
        stmt = stmt.where(Ticket.status == status)
    if priority:
        stmt = stmt.where(Ticket.priority == priority)
    if assignee == "none":
        stmt = stmt.where(Ticket.assignee_user_id.is_(None))
    elif assignee:
        stmt = stmt.where(Ticket.assignee_user_id == UUID(assignee))
    if integration_id is not None:
        stmt = stmt.where(Ticket.source_integration_id == integration_id)
    if q:
        stmt = stmt.where(Ticket.subject.ilike(f"%{q}%"))
    stmt = stmt.order_by(Ticket.created_at.desc(), Ticket.number.desc())

    offset = int(cursor) if cursor else 0
    limit = max(1, min(limit, 200))
    rows = (
        await db.execute(stmt.offset(offset).limit(limit + 1))
    ).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    requesters: dict[UUID, Requester] = {}
    requester_ids = {t.requester_id for t in rows if t.requester_id}
    if requester_ids:
        loaded = (
            await db.execute(select(Requester).where(Requester.id.in_(requester_ids)))
        ).scalars().all()
        requesters = {r.id: r for r in loaded}

    data = [ticket_read(t, requesters.get(t.requester_id)) for t in rows]
    return TicketListRead(data=data, next_cursor=str(offset + limit) if has_more else None)


async def add_message(
    db: AsyncSession, ctx: TenantContext, ticket: Ticket, payload: TicketMessageCreate
) -> TicketMessageRead:
    agent = ctx.actor_type == "user"
    message = TicketMessage(
        ticket_id=ticket.id,
        workspace_id=ticket.workspace_id,
        author_type="agent" if agent else "requester",
        author_user_id=ctx.user.id if agent and ctx.user else None,
        visibility=payload.visibility,
        body=payload.body,
    )
    db.add(message)
    await db.flush()
    try:
        await attachments_svc.bind_attachments(
            db,
            workspace_id=ticket.workspace_id,
            ticket_id=ticket.id,
            message_id=message.id,
            attachment_ids=payload.attachment_ids,
        )
    except ValueError:
        await db.rollback()
        raise
    if agent and payload.visibility == "public" and ticket.first_response_at is None:
        ticket.first_response_at = utcnow()
    if not agent and ticket.status == "pending":
        ticket.status = "open"
    await record_event(
        db,
        ticket=ticket,
        type="ticket.replied",
        actor_type=ctx.actor_type,
        actor_id=ctx.user.id if ctx.user else (ctx.integration.id if ctx.integration else None),
        data={"visibility": payload.visibility},
    )
    await webhooks_svc.enqueue_event(
        db, ticket=ticket, event="ticket.replied", data={"visibility": payload.visibility}
    )
    await db.commit()
    await db.refresh(message)
    if payload.visibility == "public":
        # Human hand-off: an agent reply notifies the requester; a requester
        # reply notifies the workspace's agents (recipient None → Notifyr).
        requester = await _requester_for(db, ticket)
        await notifyr_svc.notify_ticket_event(
            db,
            workspace=ctx.workspace,
            ticket=ticket,
            event=notifyr_svc.TICKET_REPLIED,
            recipient=requester.email if (agent and requester) else None,
            variables={"visibility": payload.visibility},
        )
    grouped = attachments_svc.group_by_message(await attachments_svc.load_attachments(db, ticket.id))
    return message_read(message, grouped.get(message.id, []))


async def apply_update(
    db: AsyncSession, ctx: TenantContext, ticket: Ticket, payload: TicketUpdate
) -> TicketRead:
    previous_status = ticket.status
    previous_assignee = ticket.assignee_user_id
    if payload.subject is not None:
        ticket.subject = payload.subject.strip()
    if payload.priority is not None:
        ticket.priority = payload.priority
    if payload.tags is not None:
        ticket.tags = payload.tags
    if payload.assignee_user_id is not None:
        ticket.assignee_user_id = payload.assignee_user_id
    if payload.status is not None:
        ticket.status = payload.status
        if payload.status in ("resolved", "closed"):
            ticket.resolved_at = ticket.resolved_at or utcnow()
        else:
            ticket.resolved_at = None
    await record_event(
        db,
        ticket=ticket,
        type="ticket.updated",
        actor_type=ctx.actor_type,
        actor_id=ctx.user.id if ctx.user else (ctx.integration.id if ctx.integration else None),
        data=payload.model_dump(exclude_none=True),
    )
    if payload.status is not None and ticket.status != previous_status:
        await webhooks_svc.enqueue_event(
            db,
            ticket=ticket,
            event="ticket.status_changed",
            data={"from": previous_status, "to": ticket.status},
        )
    if payload.assignee_user_id is not None and ticket.assignee_user_id != previous_assignee:
        await webhooks_svc.enqueue_event(
            db,
            ticket=ticket,
            event="ticket.assigned",
            data={"assignee_user_id": str(ticket.assignee_user_id)},
        )
    await db.commit()
    await db.refresh(ticket)
    return ticket_read(ticket, await _requester_for(db, ticket))


async def set_status(
    db: AsyncSession, ctx: TenantContext, ticket: Ticket, status: str, *, event: str
) -> TicketRead:
    ticket.status = status
    ticket.resolved_at = utcnow() if status in ("resolved", "closed") else None
    await record_event(
        db,
        ticket=ticket,
        type=event,
        actor_type=ctx.actor_type,
        actor_id=ctx.user.id if ctx.user else (ctx.integration.id if ctx.integration else None),
    )
    await webhooks_svc.enqueue_event(db, ticket=ticket, event=event)
    await db.commit()
    await db.refresh(ticket)
    return ticket_read(ticket, await _requester_for(db, ticket))
