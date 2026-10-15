"""SLA targets and breach detection.

A workspace sets per-priority first-response and resolution targets (in minutes)
under ``workspace.settings["sla"]``. Due timestamps are stamped on the ticket at
creation; a worker sweep marks overdue tickets as breached and raises a
``sla.breached`` event. Business hours are not modelled yet (calendar hours).
"""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ticket, Workspace, utcnow
from app.schemas import SlaSettingsRead, SlaSettingsUpdate
from app.services import webhooks as webhooks_svc

logger = logging.getLogger(__name__)

PRIORITIES = ("low", "normal", "high", "urgent")

# Minutes, by priority, when a workspace has not set its own policy.
DEFAULT_FIRST_RESPONSE = {"low": 480, "normal": 240, "high": 60, "urgent": 30}
DEFAULT_RESOLUTION = {"low": 4320, "normal": 2880, "high": 1440, "urgent": 480}


def _minutes(raw: dict | None, default: dict[str, int]) -> dict[str, int]:
    result = dict(default)
    for priority in PRIORITIES:
        value = (raw or {}).get(priority)
        try:
            if value is not None:
                result[priority] = max(0, int(value))
        except (TypeError, ValueError):
            pass
    return result


def load_policy(workspace: Workspace) -> tuple[dict[str, int], dict[str, int]]:
    sla = (workspace.settings or {}).get("sla") or {}
    return (
        _minutes(sla.get("first_response_minutes"), DEFAULT_FIRST_RESPONSE),
        _minutes(sla.get("resolution_minutes"), DEFAULT_RESOLUTION),
    )


def sla_settings(workspace: Workspace) -> SlaSettingsRead:
    first, resolution = load_policy(workspace)
    return SlaSettingsRead(first_response_minutes=first, resolution_minutes=resolution)


def apply_policy(workspace: Workspace, ticket: Ticket) -> None:
    """Stamp the due timestamps for a freshly created ticket."""
    first, resolution = load_policy(workspace)
    now = ticket.created_at or utcnow()
    ticket.first_response_due_at = now + timedelta(minutes=first.get(ticket.priority, first["normal"]))
    ticket.resolution_due_at = now + timedelta(minutes=resolution.get(ticket.priority, resolution["normal"]))


async def update_settings(
    db: AsyncSession, workspace: Workspace, payload: SlaSettingsUpdate
) -> SlaSettingsRead:
    settings = dict(workspace.settings or {})
    sla = dict(settings.get("sla") or {})
    if payload.first_response_minutes is not None:
        sla["first_response_minutes"] = payload.first_response_minutes
    if payload.resolution_minutes is not None:
        sla["resolution_minutes"] = payload.resolution_minutes
    settings["sla"] = sla
    workspace.settings = settings
    await db.commit()
    await db.refresh(workspace)
    return sla_settings(workspace)


async def sweep_breaches(db: AsyncSession, *, limit: int = 100) -> int:
    """Mark overdue, unbreached, still-open tickets and raise ``sla.breached``."""
    now = utcnow()
    rows = (
        await db.execute(
            select(Ticket)
            .where(
                Ticket.sla_breached_at.is_(None),
                Ticket.status.in_(("open", "pending")),
                Ticket.resolution_due_at.is_not(None),
                Ticket.resolution_due_at <= now,
            )
            .order_by(Ticket.resolution_due_at)
            .limit(limit)
        )
    ).scalars().all()
    for ticket in rows:
        ticket.sla_breached_at = now
        from app.services import tickets as tickets_svc  # local import avoids a cycle

        await tickets_svc.record_event(
            db,
            ticket=ticket,
            type="sla.breached",
            actor_type="system",
            data={"resolution_due_at": ticket.resolution_due_at.isoformat() if ticket.resolution_due_at else None},
        )
        await webhooks_svc.enqueue_event(db, ticket=ticket, event="sla.breached")
    if rows:
        await db.commit()
    return len(rows)
