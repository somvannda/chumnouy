"""CSAT: a requester's satisfaction rating for a ticket (one per ticket)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CsatResponse, Ticket, Workspace, utcnow
from app.schemas import CsatRead, CsatSubmit


def csat_read(row: CsatResponse) -> CsatRead:
    return CsatRead(
        ticket_id=row.ticket_id,
        rating=row.rating,
        comment=row.comment,
        created_at=row.created_at,
    )


async def submit(
    db: AsyncSession, workspace: Workspace, ticket: Ticket, payload: CsatSubmit
) -> CsatRead:
    row = (
        await db.execute(select(CsatResponse).where(CsatResponse.ticket_id == ticket.id))
    ).scalar_one_or_none()
    if row is None:
        row = CsatResponse(
            workspace_id=workspace.id,
            ticket_id=ticket.id,
            rating=payload.rating,
            comment=payload.comment,
        )
        db.add(row)
    else:
        row.rating = payload.rating
        row.comment = payload.comment
        row.created_at = utcnow()
    await db.commit()
    await db.refresh(row)
    return csat_read(row)


async def aggregates(db: AsyncSession, workspace_id: UUID) -> tuple[int, float | None]:
    """Return ``(responses, positive_pct)`` for the workspace."""
    ratings = (
        await db.execute(
            select(CsatResponse.rating).where(CsatResponse.workspace_id == workspace_id)
        )
    ).scalars().all()
    total = len(ratings)
    if total == 0:
        return 0, None
    positive = sum(1 for rating in ratings if rating == "up")
    return total, round(positive / total * 100, 1)
