"""Ticket presence: who is currently viewing a ticket.

A console client heartbeats; viewers seen within the window are returned, so the
UI can warn about a collision (two agents on the same ticket).
"""
from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TicketPresence, utcnow

PRESENCE_WINDOW_SECONDS = 60


async def heartbeat(db: AsyncSession, ticket_id: UUID, user_id: UUID) -> None:
    row = (
        await db.execute(
            select(TicketPresence).where(
                TicketPresence.ticket_id == ticket_id, TicketPresence.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(TicketPresence(ticket_id=ticket_id, user_id=user_id))
    else:
        row.last_seen_at = utcnow()
    await db.commit()


async def viewers(db: AsyncSession, ticket_id: UUID) -> list[UUID]:
    since = utcnow() - timedelta(seconds=PRESENCE_WINDOW_SECONDS)
    rows = (
        await db.execute(
            select(TicketPresence.user_id).where(
                TicketPresence.ticket_id == ticket_id, TicketPresence.last_seen_at >= since
            )
        )
    ).scalars().all()
    return list(rows)
