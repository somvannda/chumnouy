"""Macros: named action bundles an agent applies to a ticket on demand.

Actions reuse the trigger DSL (``services/triggers``); applying a macro records a
``macro.applied`` audit event and raises the usual status/assignee webhooks.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import TenantContext
from app.models import Macro, Ticket
from app.schemas import MacroCreate, MacroRead, MacroUpdate, TicketRead
from app.services import tickets as tickets_svc
from app.services import triggers as triggers_svc
from app.services import webhooks as webhooks_svc


def macro_read(macro: Macro) -> MacroRead:
    return MacroRead(
        id=macro.id,
        name=macro.name,
        actions=list(macro.actions or []),
        created_at=macro.created_at,
        updated_at=macro.updated_at,
    )


async def list_macros(db: AsyncSession, workspace_id: UUID) -> list[MacroRead]:
    rows = (
        await db.execute(
            select(Macro).where(Macro.workspace_id == workspace_id).order_by(Macro.name)
        )
    ).scalars().all()
    return [macro_read(row) for row in rows]


async def load_macro(db: AsyncSession, workspace_id: UUID, macro_id: UUID) -> Macro | None:
    return (
        await db.execute(
            select(Macro).where(Macro.id == macro_id, Macro.workspace_id == workspace_id)
        )
    ).scalar_one_or_none()


async def create_macro(db: AsyncSession, workspace_id: UUID, payload: MacroCreate) -> MacroRead:
    macro = Macro(
        workspace_id=workspace_id,
        name=payload.name.strip(),
        actions=[a.model_dump() for a in payload.actions],
    )
    db.add(macro)
    await db.commit()
    await db.refresh(macro)
    return macro_read(macro)


async def update_macro(db: AsyncSession, macro: Macro, payload: MacroUpdate) -> MacroRead:
    if payload.name is not None:
        macro.name = payload.name.strip()
    if payload.actions is not None:
        macro.actions = [a.model_dump() for a in payload.actions]
    await db.commit()
    await db.refresh(macro)
    return macro_read(macro)


async def delete_macro(db: AsyncSession, macro: Macro) -> None:
    await db.delete(macro)
    await db.commit()


async def apply_macro(db: AsyncSession, ctx: TenantContext, ticket: Ticket, macro: Macro) -> TicketRead:
    previous_status = ticket.status
    previous_assignee = ticket.assignee_user_id
    previous_team = ticket.team_id

    changes = triggers_svc._apply_actions(ticket, macro.actions)
    changes += await triggers_svc.apply_notify_actions(
        db, ticket, macro.actions, source=f"macro:{macro.name}"
    )

    await tickets_svc.record_event(
        db,
        ticket=ticket,
        type="macro.applied",
        actor_type=ctx.actor_type,
        actor_id=ctx.user.id if ctx.user else (ctx.integration.id if ctx.integration else None),
        data={"macro": macro.name, "changes": changes},
    )
    if ticket.status != previous_status:
        await webhooks_svc.enqueue_event(
            db,
            ticket=ticket,
            event="ticket.status_changed",
            data={"from": previous_status, "to": ticket.status, "macro": macro.name},
        )
    if ticket.assignee_user_id != previous_assignee or ticket.team_id != previous_team:
        await webhooks_svc.enqueue_event(
            db,
            ticket=ticket,
            event="ticket.assigned",
            data={
                "assignee_user_id": str(ticket.assignee_user_id) if ticket.assignee_user_id else None,
                "team_id": str(ticket.team_id) if ticket.team_id else None,
                "macro": macro.name,
            },
        )
    await db.commit()
    await db.refresh(ticket)
    return tickets_svc.ticket_read(ticket, await tickets_svc._requester_for(db, ticket))
