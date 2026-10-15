"""Bulk actions over a list of tickets (assign/status/priority/tags/team).

Applied in one transaction; only the caller's workspace tickets are touched.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import TenantContext
from app.models import Ticket, utcnow
from app.schemas import BulkResult, BulkUpdate
from app.services import tickets as tickets_svc
from app.services import webhooks as webhooks_svc


async def apply_bulk(db: AsyncSession, ctx: TenantContext, payload: BulkUpdate) -> BulkResult:
    action = payload.action
    tickets = (
        await db.execute(
            select(Ticket).where(
                Ticket.workspace_id == ctx.workspace.id,
                Ticket.id.in_(payload.ticket_ids),
            )
        )
    ).scalars().all()

    actor_id = ctx.user.id if ctx.user else (ctx.integration.id if ctx.integration else None)
    for ticket in tickets:
        previous_status = ticket.status
        previous_assignee = ticket.assignee_user_id
        previous_team = ticket.team_id

        if action.status is not None:
            ticket.status = action.status
            ticket.resolved_at = (
                ticket.resolved_at or utcnow()
                if action.status in ("resolved", "closed")
                else None
            )
        if action.priority is not None:
            ticket.priority = action.priority
        if action.assignee_user_id is not None:
            ticket.assignee_user_id = action.assignee_user_id
        if action.team_id is not None:
            ticket.team_id = action.team_id
        if action.add_tags:
            ticket.tags = list(dict.fromkeys([*(ticket.tags or []), *action.add_tags]))
        if action.remove_tags:
            ticket.tags = [tag for tag in (ticket.tags or []) if tag not in action.remove_tags]

        await tickets_svc.record_event(
            db,
            ticket=ticket,
            type="ticket.updated",
            actor_type=ctx.actor_type,
            actor_id=actor_id,
            data={"bulk": True, **action.model_dump(mode="json", exclude_none=True)},
        )
        if action.status is not None and ticket.status != previous_status:
            await webhooks_svc.enqueue_event(
                db,
                ticket=ticket,
                event="ticket.status_changed",
                data={"from": previous_status, "to": ticket.status, "bulk": True},
            )
        if action.assignee_user_id is not None and ticket.assignee_user_id != previous_assignee:
            await webhooks_svc.enqueue_event(
                db,
                ticket=ticket,
                event="ticket.assigned",
                data={"assignee_user_id": str(ticket.assignee_user_id), "bulk": True},
            )
        if action.team_id is not None and ticket.team_id != previous_team:
            await webhooks_svc.enqueue_event(
                db,
                ticket=ticket,
                event="ticket.assigned",
                data={"team_id": str(ticket.team_id), "bulk": True},
            )

    await db.commit()
    return BulkResult(updated=len(tickets), ticket_ids=[ticket.id for ticket in tickets])
