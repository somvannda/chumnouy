"""Per-workspace quotas.

A workspace can cap its monthly ticket volume and its seat count under
``workspace.settings["quota"]`` (``tickets_per_month``, ``seats``; 0 or absent =
unlimited). Exceeding a quota is a client-fixable condition, so the endpoints
turn it into a 4xx (429 for tickets, 409 for seats).
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Membership, Ticket, Workspace


def _limit(workspace: Workspace, key: str) -> int:
    quota = (workspace.settings or {}).get("quota") or {}
    try:
        return int(quota.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def ticket_quota(workspace: Workspace) -> int:
    return _limit(workspace, "tickets_per_month")


def seat_quota(workspace: Workspace) -> int:
    return _limit(workspace, "seats")


async def tickets_this_month(db: AsyncSession, workspace_id: UUID) -> int:
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return int(
        (
            await db.execute(
                select(func.count(Ticket.id)).where(
                    Ticket.workspace_id == workspace_id, Ticket.created_at >= start
                )
            )
        ).scalar()
        or 0
    )


async def enforce_ticket_quota(db: AsyncSession, workspace: Workspace) -> None:
    """Raise 429 when the workspace has used its monthly ticket allowance."""
    limit = ticket_quota(workspace)
    if limit <= 0:
        return
    if await tickets_this_month(db, workspace.id) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Monthly ticket quota reached",
        )


async def seats_used(db: AsyncSession, workspace_id: UUID) -> int:
    """Active members (pending invitations are not seats yet)."""
    return int(
        (
            await db.execute(
                select(func.count(Membership.id)).where(
                    Membership.workspace_id == workspace_id, Membership.status == "active"
                )
            )
        ).scalar()
        or 0
    )


async def enforce_seat_quota(db: AsyncSession, workspace: Workspace) -> None:
    """Raise 409 when adding another member would exceed the seat allowance."""
    limit = seat_quota(workspace)
    if limit <= 0:
        return
    if await seats_used(db, workspace.id) >= limit:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seat quota reached",
        )
