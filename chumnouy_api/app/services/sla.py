"""SLA targets and breach detection.

A workspace sets per-priority first-response and resolution targets (in minutes)
under ``workspace.settings["sla"]``, and may override any priority per team under
``workspace.settings["sla"]["teams"][<team_id>]``. Due timestamps are stamped on
the ticket at creation — and re-stamped when its team changes — from the ticket's
team policy, falling back to the workspace policy. A worker sweep marks overdue
tickets as breached and raises a ``sla.breached`` event. Targets count calendar
hours unless business hours are enabled.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ticket, Workspace, utcnow
from app.schemas import SlaSettingsRead, SlaSettingsUpdate, SlaTeamPolicy
from app.services import business_hours as business_hours_svc
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


def _team_overrides(sla: dict) -> dict:
    teams = sla.get("teams")
    return teams if isinstance(teams, dict) else {}


def load_policy(
    workspace: Workspace, team_id: UUID | str | None = None
) -> tuple[dict[str, int], dict[str, int]]:
    """The effective targets: the workspace policy, then any team override."""
    sla = (workspace.settings or {}).get("sla") or {}
    first = _minutes(sla.get("first_response_minutes"), DEFAULT_FIRST_RESPONSE)
    resolution = _minutes(sla.get("resolution_minutes"), DEFAULT_RESOLUTION)
    if team_id is not None:
        override = _team_overrides(sla).get(str(team_id))
        if isinstance(override, dict):
            first = _minutes(override.get("first_response_minutes"), first)
            resolution = _minutes(override.get("resolution_minutes"), resolution)
    return first, resolution


def sla_settings(workspace: Workspace) -> SlaSettingsRead:
    first, resolution = load_policy(workspace)
    stored = _team_overrides((workspace.settings or {}).get("sla") or {})
    teams = {
        str(team_id): SlaTeamPolicy(
            first_response_minutes=_minutes(policy.get("first_response_minutes"), {}),
            resolution_minutes=_minutes(policy.get("resolution_minutes"), {}),
        )
        for team_id, policy in stored.items()
        if isinstance(policy, dict)
    }
    return SlaSettingsRead(
        first_response_minutes=first, resolution_minutes=resolution, teams=teams
    )


def _due(workspace: Workspace, start, minutes: int):
    """Add ``minutes`` to ``start``, honouring business hours when enabled."""
    bh = (workspace.settings or {}).get("business_hours") or {}
    if bh.get("enabled"):
        schedule = business_hours_svc.parse_schedule(bh.get("days"))
        if schedule:
            return business_hours_svc.add_business_minutes(
                start, minutes, schedule, bh.get("timezone")
            )
    return start + timedelta(minutes=minutes)


def apply_policy(workspace: Workspace, ticket: Ticket) -> None:
    """Stamp the due timestamps for a ticket (re-stamped when its team changes)."""
    first, resolution = load_policy(workspace, ticket.team_id)
    now = ticket.created_at or utcnow()
    ticket.first_response_due_at = _due(workspace, now, first.get(ticket.priority, first["normal"]))
    ticket.resolution_due_at = _due(workspace, now, resolution.get(ticket.priority, resolution["normal"]))


def _clean_minutes(raw: dict | None) -> dict[str, int]:
    values: dict[str, int] = {}
    for priority, value in (raw or {}).items():
        if priority not in PRIORITIES:
            continue
        try:
            values[priority] = max(0, int(value))
        except (TypeError, ValueError):
            continue
    return values


async def update_settings(
    db: AsyncSession, workspace: Workspace, payload: SlaSettingsUpdate
) -> SlaSettingsRead:
    settings = dict(workspace.settings or {})
    sla = dict(settings.get("sla") or {})
    if payload.first_response_minutes is not None:
        sla["first_response_minutes"] = payload.first_response_minutes
    if payload.resolution_minutes is not None:
        sla["resolution_minutes"] = payload.resolution_minutes
    if payload.teams is not None:
        teams: dict[str, dict] = {}
        for team_id, policy in payload.teams.items():
            try:
                key = str(UUID(str(team_id)))
            except (TypeError, ValueError):
                continue
            teams[key] = {
                "first_response_minutes": _clean_minutes(policy.first_response_minutes),
                "resolution_minutes": _clean_minutes(policy.resolution_minutes),
            }
        sla["teams"] = teams
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
