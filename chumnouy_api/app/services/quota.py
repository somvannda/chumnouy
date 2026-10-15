"""Per-workspace quotas.

A workspace can cap its monthly ticket volume under
``workspace.settings["quota"]["tickets_per_month"]`` (0 or absent = unlimited).
Exceeding it is a client-fixable condition, so the endpoints turn it into a 429.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ticket, Workspace


def ticket_quota(workspace: Workspace) -> int:
    quota = (workspace.settings or {}).get("quota") or {}
    try:
        return int(quota.get("tickets_per_month") or 0)
    except (TypeError, ValueError):
        return 0


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
