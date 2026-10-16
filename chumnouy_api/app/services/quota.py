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

from app.models import Membership, Ticket, TicketAttachment, Workspace

STORAGE_BYTES_PER_MB = 1024 * 1024


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


def storage_quota(workspace: Workspace) -> int:
    """Storage cap in whole megabytes (0 or absent = unlimited)."""
    return _limit(workspace, "storage_mb")


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


async def storage_used_bytes(db: AsyncSession, workspace_id: UUID) -> int:
    """Total attachment bytes recorded for the workspace."""
    return int(
        (
            await db.execute(
                select(func.coalesce(func.sum(TicketAttachment.byte_size), 0)).where(
                    TicketAttachment.workspace_id == workspace_id
                )
            )
        ).scalar()
        or 0
    )


async def enforce_storage_quota(
    db: AsyncSession, workspace: Workspace, *, additional_bytes: int = 0
) -> None:
    """Raise 413 when an upload would push the workspace over its storage cap."""
    limit = storage_quota(workspace)
    if limit <= 0:
        return
    used = await storage_used_bytes(db, workspace.id)
    if used + max(0, additional_bytes) > limit * STORAGE_BYTES_PER_MB:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Storage quota reached",
        )
