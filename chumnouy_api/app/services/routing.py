"""Ticket routing: pick an assignee by strategy.

- ``round_robin``: the candidate who was assigned a ticket least recently (a
  never-assigned agent first) — no cursor state needed.
- ``load_balanced``: the candidate with the fewest open tickets.
- ``team``: assign the ticket to a team (no individual).
- ``skill``: skill-filtered candidates, then load-balanced.

Candidates are the given team's members, or the workspace's active agents, and
are narrowed to agents holding the ticket's ``required_skills`` (or the explicit
``skill`` on the request). If nobody matches, routing falls back to the unfiltered
candidates so a ticket is never left unassigned.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import TenantContext
from app.models import Membership, TeamMember, Ticket, utcnow
from app.schemas import TicketAssign, TicketRead
from app.services import tickets as tickets_svc
from app.services import webhooks as webhooks_svc

AGENT_ROLES = ("owner", "admin", "team_lead", "agent")
OPEN_STATUSES = ("open", "pending")
ASSIGN_STRATEGIES = ("round_robin", "load_balanced", "skill")


def _wanted_skills(payload: TicketAssign, ticket: Ticket) -> list[str]:
    if payload.skill:
        return [payload.skill.strip().lower()]
    return [str(skill).strip().lower() for skill in (ticket.required_skills or []) if str(skill).strip()]


async def _candidates(
    db: AsyncSession,
    workspace_id: UUID,
    team_id: UUID | None,
    skills: list[str] | None = None,
) -> list[UUID]:
    """Candidate agents, narrowed to those holding every requested skill."""
    if team_id is not None:
        rows = (
            await db.execute(select(TeamMember.user_id).where(TeamMember.team_id == team_id))
        ).scalars().all()
        user_ids = list(rows)
    else:
        rows = (
            await db.execute(
                select(Membership.user_id).where(
                    Membership.workspace_id == workspace_id,
                    Membership.status == "active",
                    Membership.role.in_(AGENT_ROLES),
                )
            )
        ).scalars().all()
        user_ids = list(rows)
    if not user_ids or not skills:
        return user_ids
    rows = (
        await db.execute(
            select(Membership.user_id, Membership.skills).where(
                Membership.workspace_id == workspace_id, Membership.user_id.in_(user_ids)
            )
        )
    ).all()
    held = {
        user_id: {str(skill).strip().lower() for skill in (skills_row or [])}
        for user_id, skills_row in rows
    }
    matched = [user_id for user_id in user_ids if all(skill in held.get(user_id, set()) for skill in skills)]
    return matched or user_ids


async def _round_robin(db: AsyncSession, workspace_id: UUID, candidates: list[UUID]) -> UUID | None:
    rows = (
        await db.execute(
            select(Ticket.assignee_user_id, func.max(Ticket.created_at))
            .where(
                Ticket.workspace_id == workspace_id,
                Ticket.assignee_user_id.in_(candidates),
            )
            .group_by(Ticket.assignee_user_id)
        )
    ).all()
    last = {user_id: when for user_id, when in rows}
    ordered = sorted(candidates, key=lambda user_id: (last.get(user_id) is not None, last.get(user_id)))
    return ordered[0] if ordered else None


async def _load_balanced(db: AsyncSession, workspace_id: UUID, candidates: list[UUID]) -> UUID | None:
    rows = (
        await db.execute(
            select(Ticket.assignee_user_id, func.count(Ticket.id))
            .where(
                Ticket.workspace_id == workspace_id,
                Ticket.status.in_(OPEN_STATUSES),
                Ticket.assignee_user_id.in_(candidates),
            )
            .group_by(Ticket.assignee_user_id)
        )
    ).all()
    counts = {user_id: count for user_id, count in rows}
    ordered = sorted(candidates, key=lambda user_id: counts.get(user_id, 0))
    return ordered[0] if ordered else None


async def assign(db: AsyncSession, ctx: TenantContext, ticket: Ticket, payload: TicketAssign) -> TicketRead:
    previous = (ticket.assignee_user_id, ticket.team_id)

    if payload.team_id is not None:
        ticket.team_id = payload.team_id

    if payload.user_id is not None:
        ticket.assignee_user_id = payload.user_id
    elif payload.strategy in ASSIGN_STRATEGIES:
        candidates = await _candidates(
            db, ctx.workspace.id, payload.team_id, _wanted_skills(payload, ticket)
        )
        if payload.strategy == "round_robin":
            chosen = await _round_robin(db, ctx.workspace.id, candidates)
        else:
            # ``skill`` and ``load_balanced`` share the fewest-open-tickets pick.
            chosen = await _load_balanced(db, ctx.workspace.id, candidates)
        if chosen is not None:
            ticket.assignee_user_id = chosen

    if (ticket.assignee_user_id, ticket.team_id) != previous:
        await tickets_svc.record_event(
            db,
            ticket=ticket,
            type="ticket.assigned",
            actor_type=ctx.actor_type,
            actor_id=ctx.user.id if ctx.user else (ctx.integration.id if ctx.integration else None),
            data={
                "assignee_user_id": str(ticket.assignee_user_id) if ticket.assignee_user_id else None,
                "team_id": str(ticket.team_id) if ticket.team_id else None,
                "strategy": payload.strategy,
                "skill": payload.skill,
            },
        )
        await webhooks_svc.enqueue_event(
            db,
            ticket=ticket,
            event="ticket.assigned",
            data={
                "assignee_user_id": str(ticket.assignee_user_id) if ticket.assignee_user_id else None,
                "team_id": str(ticket.team_id) if ticket.team_id else None,
            },
        )
        ticket.updated_at = utcnow()
    await db.commit()
    await db.refresh(ticket)
    return tickets_svc.ticket_read(ticket, await tickets_svc._requester_for(db, ticket))
