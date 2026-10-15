"""Ticket attachments: staged uploads and the claim that binds them.

A file is uploaded *unowned* (``ticket_id`` is NULL) while a requester or agent
is still composing, then claimed by the request/reply that references it. Only
the caller's own, still-unowned rows can be claimed, so one workspace can never
attach another workspace's media and a staged row cannot be claimed twice.

Ported from Chmaba POS ``app/services/support_tickets.py`` (``bind_attachments``
and the attachment half of ``ticket_detail_read``), renamed to ``workspace_id``.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import TenantContext
from app.models import Ticket, TicketAttachment
from app.schemas import AttachmentRead


def attachment_read(attachment: TicketAttachment) -> AttachmentRead:
    return AttachmentRead(
        id=attachment.id,
        url=attachment.url,
        content_type=attachment.content_type,
        kind=attachment.kind,
        byte_size=attachment.byte_size,
        original_filename=attachment.original_filename,
        position=attachment.position,
    )


def group_by_message(
    attachments: list[TicketAttachment],
) -> dict[UUID | None, list[AttachmentRead]]:
    """Group claimed attachments by ``message_id``; ``None`` is the opening question."""
    grouped: dict[UUID | None, list[AttachmentRead]] = {}
    for attachment in attachments:
        grouped.setdefault(attachment.message_id, []).append(attachment_read(attachment))
    return grouped


async def load_attachments(db: AsyncSession, ticket_id: UUID) -> list[TicketAttachment]:
    rows = (
        await db.execute(
            select(TicketAttachment)
            .where(TicketAttachment.ticket_id == ticket_id)
            .order_by(TicketAttachment.position, TicketAttachment.created_at)
        )
    ).scalars().all()
    return list(rows)


async def bind_attachments(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    ticket_id: UUID,
    message_id: UUID | None,
    attachment_ids: list[UUID],
) -> list[TicketAttachment]:
    """Claim staged uploads for a ticket and (optionally) one of its messages.

    Uploads start unowned (``ticket_id`` is NULL) so a client can attach files to
    the request or reply it is still composing. Only the caller's own,
    still-unowned rows are claimed; an unknown, foreign or already-claimed id
    raises ``ValueError`` which the endpoint turns into a 400. That keeps one
    tenant from attaching another tenant's media, and stops a staged row from
    being claimed twice.
    """
    if not attachment_ids:
        return []
    unique_ids = list(dict.fromkeys(attachment_ids))
    if len(unique_ids) > settings.max_attachments_per_message:
        raise ValueError(
            f"At most {settings.max_attachments_per_message} attachments per message"
        )
    rows = (
        await db.execute(
            select(TicketAttachment).where(
                TicketAttachment.id.in_(unique_ids),
                TicketAttachment.workspace_id == workspace_id,
                TicketAttachment.ticket_id.is_(None),
            )
        )
    ).scalars().all()
    by_id = {row.id: row for row in rows}
    if len(by_id) != len(unique_ids):
        raise ValueError("One or more attachments could not be found")
    bound: list[TicketAttachment] = []
    for position, attachment_id in enumerate(unique_ids):
        row = by_id[attachment_id]
        row.ticket_id = ticket_id
        row.message_id = message_id
        row.position = position
        bound.append(row)
    return bound


async def stage_attachment(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    url: str,
    sha256: str,
    content_type: str | None,
    kind: str = "image",
    byte_size: int,
    original_filename: str | None,
) -> AttachmentRead:
    """Create an unowned attachment row for a freshly stored file."""
    attachment = TicketAttachment(
        workspace_id=ctx.workspace.id,
        url=url,
        sha256=sha256,
        content_type=content_type,
        kind=kind,
        byte_size=byte_size,
        original_filename=original_filename,
        created_by=ctx.user.id if ctx.user else None,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment_read(attachment)


async def claim_attachments(
    db: AsyncSession, ctx: TenantContext, ticket: Ticket, attachment_ids: list[UUID]
) -> list[AttachmentRead]:
    """Bind staged uploads to the ticket itself (no message), as opening files."""
    bound = await bind_attachments(
        db,
        workspace_id=ctx.workspace.id,
        ticket_id=ticket.id,
        message_id=None,
        attachment_ids=attachment_ids,
    )
    await db.commit()
    return [attachment_read(row) for row in bound]
