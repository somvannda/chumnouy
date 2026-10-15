"""Inbound email → ticket.

Notifyr owns the mail transport and parses the message; it posts the result here
(authenticated with a Chumnouy API key). A message is threaded onto an existing
ticket via ``in_reply_to`` — or the sender's latest open ticket — otherwise it
opens a new ticket. The sender is created as a requester on first contact.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ticket, TicketMessage, Workspace
from app.schemas import InboundEmailCreate, RequesterInput, TicketDetailRead
from app.services import notifyr as notifyr_svc
from app.services import quota as quota_svc
from app.services import sla as sla_svc
from app.services import tickets as tickets_svc
from app.services import webhooks as webhooks_svc
from app.services.sanitize import render_body

OPEN_STATUSES = ("open", "pending")


async def _ticket_by_message(
    db: AsyncSession, workspace_id: UUID, message_id: str | None
) -> Ticket | None:
    if not message_id:
        return None
    row = (
        await db.execute(
            select(TicketMessage).where(
                TicketMessage.workspace_id == workspace_id,
                TicketMessage.email_message_id == message_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return (
        await db.execute(select(Ticket).where(Ticket.id == row.ticket_id))
    ).scalar_one_or_none()


async def _open_ticket_for(
    db: AsyncSession, workspace_id: UUID, requester_id: UUID
) -> Ticket | None:
    return (
        await db.execute(
            select(Ticket)
            .where(
                Ticket.workspace_id == workspace_id,
                Ticket.requester_id == requester_id,
                Ticket.status.in_(OPEN_STATUSES),
            )
            .order_by(Ticket.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def handle_inbound_email(
    db: AsyncSession, workspace: Workspace, payload: InboundEmailCreate
) -> TicketDetailRead:
    body = render_body(payload.body, payload.body_format)
    requester = await tickets_svc.upsert_requester(
        db,
        workspace.id,
        RequesterInput(
            external_id=str(payload.from_email).lower(),
            email=str(payload.from_email),
            name=payload.from_name,
        ),
    )
    await db.flush()

    ticket = await _ticket_by_message(db, workspace.id, payload.in_reply_to)
    if ticket is None:
        ticket = await _open_ticket_for(db, workspace.id, requester.id)

    if ticket is not None:
        message = TicketMessage(
            ticket_id=ticket.id,
            workspace_id=workspace.id,
            author_type="requester",
            visibility="public",
            body=body,
            body_format=payload.body_format,
            email_message_id=payload.message_id,
        )
        db.add(message)
        await db.flush()
        if ticket.status == "pending":
            ticket.status = "open"
        await tickets_svc.record_event(
            db, ticket=ticket, type="ticket.replied", actor_type="requester", data={"channel": "email"}
        )
        await webhooks_svc.enqueue_event(
            db, ticket=ticket, event="ticket.replied", data={"channel": "email"}
        )
        await notifyr_svc.enqueue(
            db,
            workspace=workspace,
            ticket=ticket,
            event=notifyr_svc.TICKET_REPLIED,
            variables={"channel": "email"},
        )
        await db.commit()
        return await tickets_svc.ticket_detail(db, ticket)

    await quota_svc.enforce_ticket_quota(db, workspace)
    number, reference = await tickets_svc.next_reference(db, workspace.id)
    subject = (payload.subject or "(no subject)").strip()[:255] or "(no subject)"
    ticket = Ticket(
        workspace_id=workspace.id,
        number=number,
        reference=reference,
        subject=subject,
        status="open",
        priority="normal",
        requester_id=requester.id,
    )
    db.add(ticket)
    await db.flush()
    sla_svc.apply_policy(workspace, ticket)
    db.add(
        TicketMessage(
            ticket_id=ticket.id,
            workspace_id=workspace.id,
            author_type="requester",
            visibility="public",
            body=body,
            body_format=payload.body_format,
            email_message_id=payload.message_id,
        )
    )
    await tickets_svc.record_event(
        db,
        ticket=ticket,
        type="ticket.created",
        actor_type="requester",
        data={"channel": "email", "reference": reference},
    )
    await webhooks_svc.enqueue_event(
        db, ticket=ticket, event="ticket.created", data={"reference": reference, "channel": "email"}
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
    return await tickets_svc.ticket_detail(db, ticket)
