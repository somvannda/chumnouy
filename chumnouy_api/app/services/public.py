"""Public (requester) ticket surface.

A requester — the integrator's end user, authenticated by a portal token — can
open a ticket, list and read their own tickets, and reply. Only public messages
are ever returned; internal notes stay hidden (the ``include_system=False``
behaviour ported from Chmaba POS ``ticket_detail_read``).
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Requester, Ticket, TicketMessage, Workspace
from app.schemas import (
    PublicTicketCreate,
    PublicTicketMessageCreate,
    TicketDetailRead,
    TicketListRead,
    TicketMessageRead,
)
from app.services import attachments as attachments_svc
from app.services import notifyr as notifyr_svc
from app.services import sla as sla_svc
from app.services import tickets as tickets_svc
from app.services import webhooks as webhooks_svc
from app.services.sanitize import render_body


async def list_portal_tickets(
    db: AsyncSession, workspace_id: UUID, requester: Requester, *, limit: int = 50
) -> TicketListRead:
    rows = (
        await db.execute(
            select(Ticket)
            .where(Ticket.workspace_id == workspace_id, Ticket.requester_id == requester.id)
            .order_by(Ticket.created_at.desc())
            .limit(max(1, min(limit, 200)))
        )
    ).scalars().all()
    return TicketListRead(data=[tickets_svc.ticket_read(ticket, requester) for ticket in rows])


async def load_portal_ticket(
    db: AsyncSession, workspace_id: UUID, requester_id: UUID, ticket_id: UUID
) -> Ticket | None:
    return (
        await db.execute(
            select(Ticket).where(
                Ticket.id == ticket_id,
                Ticket.workspace_id == workspace_id,
                Ticket.requester_id == requester_id,
            )
        )
    ).scalar_one_or_none()


async def portal_ticket_detail(
    db: AsyncSession, requester: Requester, ticket: Ticket
) -> TicketDetailRead:
    messages = (
        await db.execute(
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket.id, TicketMessage.visibility == "public")
            .order_by(TicketMessage.created_at)
        )
    ).scalars().all()
    grouped = attachments_svc.group_by_message(
        await attachments_svc.load_attachments(db, ticket.id)
    )
    return TicketDetailRead(
        **tickets_svc.ticket_read(ticket, requester).model_dump(),
        messages=[tickets_svc.message_read(m, grouped.get(m.id, [])) for m in messages],
        attachments=grouped.get(None, []),
    )


async def create_portal_ticket(
    db: AsyncSession,
    workspace: Workspace,
    requester: Requester,
    payload: PublicTicketCreate,
) -> TicketDetailRead:
    number, reference = await tickets_svc.next_reference(db, workspace.id)
    ticket = Ticket(
        workspace_id=workspace.id,
        number=number,
        reference=reference,
        subject=payload.subject.strip(),
        status="open",
        priority=payload.priority,
        requester_id=requester.id,
    )
    db.add(ticket)
    await db.flush()
    sla_svc.apply_policy(workspace, ticket)
    message = TicketMessage(
        ticket_id=ticket.id,
        workspace_id=ticket.workspace_id,
        author_type="requester",
        visibility="public",
        body=render_body(payload.message, payload.message_format),
        body_format=payload.message_format,
    )
    db.add(message)
    await db.flush()
    try:
        await attachments_svc.bind_attachments(
            db,
            workspace_id=workspace.id,
            ticket_id=ticket.id,
            message_id=message.id,
            attachment_ids=payload.attachment_ids,
        )
    except ValueError:
        await db.rollback()
        raise
    await tickets_svc.record_event(db, ticket=ticket, type="ticket.created", actor_type="requester")
    await webhooks_svc.enqueue_event(
        db, ticket=ticket, event="ticket.created", data={"reference": reference}
    )
    await notifyr_svc.enqueue(
        db,
        workspace=workspace,
        ticket=ticket,
        event=notifyr_svc.TICKET_CREATED,
        variables={"reference": reference},
    )
    await db.commit()
    await db.refresh(ticket)
    return await portal_ticket_detail(db, requester, ticket)


async def add_portal_message(
    db: AsyncSession,
    workspace: Workspace,
    requester: Requester,
    ticket: Ticket,
    payload: PublicTicketMessageCreate,
) -> TicketMessageRead:
    message = TicketMessage(
        ticket_id=ticket.id,
        workspace_id=ticket.workspace_id,
        author_type="requester",
        visibility="public",
        body=render_body(payload.body, payload.body_format),
        body_format=payload.body_format,
    )
    db.add(message)
    await db.flush()
    try:
        await attachments_svc.bind_attachments(
            db,
            workspace_id=workspace.id,
            ticket_id=ticket.id,
            message_id=message.id,
            attachment_ids=payload.attachment_ids,
        )
    except ValueError:
        await db.rollback()
        raise
    if ticket.status == "pending":
        ticket.status = "open"
    await tickets_svc.record_event(
        db, ticket=ticket, type="ticket.replied", actor_type="requester", data={"visibility": "public"}
    )
    await webhooks_svc.enqueue_event(
        db, ticket=ticket, event="ticket.replied", data={"visibility": "public"}
    )
    await notifyr_svc.enqueue(
        db,
        workspace=workspace,
        ticket=ticket,
        event=notifyr_svc.TICKET_REPLIED,
        variables={"visibility": "public"},
    )
    await db.commit()
    await db.refresh(message)
    grouped = attachments_svc.group_by_message(
        await attachments_svc.load_attachments(db, ticket.id)
    )
    return tickets_svc.message_read(message, grouped.get(message.id, []))
