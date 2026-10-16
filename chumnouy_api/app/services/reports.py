"""Workspace reporting: a summary computed from the ticket table.

Computed on the fly (no rollup table) — fine at v1 volume; a daily rollup can
come later. Everything is workspace-scoped.
"""
from __future__ import annotations

from collections import Counter
from datetime import date as date_type
from datetime import datetime, time, timedelta, timezone
from statistics import mean
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ticket, utcnow
from app.schemas import ReportDaily, ReportDay, ReportSummary
from app.services import csat as csat_svc

STATUSES = ("open", "pending", "resolved", "closed")


def _minutes(start, end) -> float | None:
    if start is None or end is None:
        return None
    return (end - start).total_seconds() / 60


async def summary(db: AsyncSession, workspace_id: UUID) -> ReportSummary:
    rows = (
        await db.execute(
            select(
                Ticket.status,
                Ticket.priority,
                Ticket.assignee_user_id,
                Ticket.team_id,
                Ticket.created_at,
                Ticket.first_response_at,
                Ticket.resolved_at,
                Ticket.sla_breached_at,
                Ticket.sentiment,
            ).where(Ticket.workspace_id == workspace_id)
        )
    ).all()

    by_status: Counter = Counter()
    by_priority: Counter = Counter()
    by_assignee: Counter = Counter()
    by_team: Counter = Counter()
    by_sentiment: Counter = Counter()
    first_responses: list[float] = []
    resolutions: list[float] = []
    breached = 0
    for (
        status,
        priority,
        assignee_user_id,
        team_id,
        created,
        first_response_at,
        resolved_at,
        sla_breached_at,
        sentiment,
    ) in rows:
        by_status[status] += 1
        by_priority[priority] += 1
        by_assignee[str(assignee_user_id) if assignee_user_id else "unassigned"] += 1
        by_team[str(team_id) if team_id else "none"] += 1
        if sentiment:
            by_sentiment[sentiment] += 1
        if sla_breached_at is not None:
            breached += 1
        first = _minutes(created, first_response_at)
        if first is not None:
            first_responses.append(first)
        resolution = _minutes(created, resolved_at)
        if resolution is not None:
            resolutions.append(resolution)

    total = len(rows)
    csat_responses, csat_positive = await csat_svc.aggregates(db, workspace_id)
    return ReportSummary(
        total=total,
        by_status={status: by_status.get(status, 0) for status in STATUSES},
        by_priority=dict(by_priority),
        by_assignee=dict(by_assignee),
        by_team=dict(by_team),
        by_sentiment=dict(by_sentiment),
        breached=breached,
        sla_compliance=round((total - breached) / total * 100, 1) if total else None,
        avg_first_response_minutes=round(mean(first_responses), 1) if first_responses else None,
        avg_resolution_minutes=round(mean(resolutions), 1) if resolutions else None,
        csat_responses=csat_responses,
        csat_positive_pct=csat_positive,
    )


async def daily(db: AsyncSession, workspace_id: UUID, *, days: int = 14) -> ReportDaily:
    """Per-day activity for the last ``days`` days (dense: empty days are zero).

    Buckets in Python so the query stays portable (no dialect date functions) —
    only tickets with activity inside the window are read.
    """
    window = max(1, min(days, 90))
    today = utcnow().date()
    start_day = today - timedelta(days=window - 1)
    start = datetime.combine(start_day, time.min).replace(tzinfo=timezone.utc)

    rows = (
        await db.execute(
            select(
                Ticket.created_at,
                Ticket.first_response_at,
                Ticket.resolved_at,
                Ticket.sla_breached_at,
            ).where(
                Ticket.workspace_id == workspace_id,
                or_(
                    Ticket.created_at >= start,
                    Ticket.first_response_at >= start,
                    Ticket.resolved_at >= start,
                    Ticket.sla_breached_at >= start,
                ),
            )
        )
    ).all()

    buckets: dict[date_type, dict[str, int]] = {
        start_day + timedelta(days=offset): {"created": 0, "resolved": 0, "first_responses": 0, "breached": 0}
        for offset in range(window)
    }

    def bump(when, key: str) -> None:
        if when is None:
            return
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        bucket = buckets.get(when.astimezone(timezone.utc).date())
        if bucket is not None:
            bucket[key] += 1

    for created, first_response_at, resolved_at, breached_at in rows:
        bump(created, "created")
        bump(first_response_at, "first_responses")
        bump(resolved_at, "resolved")
        bump(breached_at, "breached")

    day_rows = [
        ReportDay(day=day, **counts) for day, counts in sorted(buckets.items())
    ]
    totals = ReportDay(
        day=today,
        created=sum(row.created for row in day_rows),
        resolved=sum(row.resolved for row in day_rows),
        first_responses=sum(row.first_responses for row in day_rows),
        breached=sum(row.breached for row in day_rows),
    )
    return ReportDaily(days=day_rows, totals=totals)
