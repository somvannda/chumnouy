"""Data retention: purge resolved tickets after a configurable window.

A workspace sets ``workspace.settings["retention"]["days"]`` (0 or absent = keep
forever). The delivery worker sweeps on every tick and permanently deletes
tickets that were resolved or closed longer ago than the window — messages,
attachments and events cascade with the ticket, so no orphan rows remain.

Data *residency* (which region the data lives in) is a deployment concern, not a
per-workspace setting, and is out of scope here.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ticket, Workspace, utcnow

logger = logging.getLogger(__name__)

PURGE_STATUSES = ("resolved", "closed")


def retention_days(workspace: Workspace) -> int:
    retention = (workspace.settings or {}).get("retention") or {}
    try:
        return max(0, int(retention.get("days") or 0))
    except (TypeError, ValueError):
        return 0


async def purge(db: AsyncSession, *, limit: int = 100) -> int:
    """Delete tickets past their workspace's retention window. Returns the count.

    Only workspaces that configured retention are considered, and only tickets
    whose ``resolved_at`` is older than the cutoff.
    """
    now = utcnow()
    workspaces = (await db.execute(select(Workspace))).scalars().all()
    windows = {
        workspace.id: retention_days(workspace)
        for workspace in workspaces
        if retention_days(workspace) > 0
    }
    if not windows:
        return 0

    purged = 0
    for workspace_id, days in windows.items():
        cutoff = now - timedelta(days=days)
        rows = (
            await db.execute(
                select(Ticket)
                .where(
                    Ticket.workspace_id == workspace_id,
                    Ticket.status.in_(PURGE_STATUSES),
                    Ticket.resolved_at.is_not(None),
                    Ticket.resolved_at < cutoff,
                )
                .order_by(Ticket.resolved_at)
                .limit(max(1, limit - purged))
            )
        ).scalars().all()
        for ticket in rows:
            await db.delete(ticket)
            purged += 1
            if purged >= limit:
                break
        if purged >= limit:
            break
    if purged:
        await db.commit()
        logger.info("retention: purged %s ticket(s)", purged)
    return purged
