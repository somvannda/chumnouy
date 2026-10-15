"""Time-based automations.

After ``after_minutes``, a ticket that is still open and matches ``conditions``
runs ``actions`` once (tracked in ``ticket_automations``). Conditions and actions
reuse the trigger DSL (``services/triggers``).
"""
from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Automation, Ticket, TicketAutomation, utcnow
from app.schemas import AutomationCreate, AutomationRead, AutomationUpdate
from app.services import tickets as tickets_svc
from app.services import triggers as triggers_svc

OPEN_STATUSES = ("open", "pending")


def automation_read(automation: Automation) -> AutomationRead:
    return AutomationRead(
        id=automation.id,
        name=automation.name,
        conditions=list(automation.conditions or []),
        actions=list(automation.actions or []),
        after_minutes=automation.after_minutes,
        position=automation.position,
        is_active=automation.is_active,
        created_at=automation.created_at,
        updated_at=automation.updated_at,
    )


async def list_automations(db: AsyncSession, workspace_id: UUID) -> list[AutomationRead]:
    rows = (
        await db.execute(
            select(Automation)
            .where(Automation.workspace_id == workspace_id)
            .order_by(Automation.position, Automation.created_at)
        )
    ).scalars().all()
    return [automation_read(row) for row in rows]


async def load_automation(
    db: AsyncSession, workspace_id: UUID, automation_id: UUID
) -> Automation | None:
    return (
        await db.execute(
            select(Automation).where(
                Automation.id == automation_id, Automation.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()


async def create_automation(
    db: AsyncSession, workspace_id: UUID, payload: AutomationCreate
) -> AutomationRead:
    automation = Automation(
        workspace_id=workspace_id,
        name=payload.name.strip(),
        conditions=[c.model_dump() for c in payload.conditions],
        actions=[a.model_dump() for a in payload.actions],
        after_minutes=payload.after_minutes,
        position=payload.position,
        is_active=payload.is_active,
    )
    db.add(automation)
    await db.commit()
    await db.refresh(automation)
    return automation_read(automation)


async def update_automation(
    db: AsyncSession, automation: Automation, payload: AutomationUpdate
) -> AutomationRead:
    if payload.name is not None:
        automation.name = payload.name.strip()
    if payload.conditions is not None:
        automation.conditions = [c.model_dump() for c in payload.conditions]
    if payload.actions is not None:
        automation.actions = [a.model_dump() for a in payload.actions]
    if payload.after_minutes is not None:
        automation.after_minutes = payload.after_minutes
    if payload.position is not None:
        automation.position = payload.position
    if payload.is_active is not None:
        automation.is_active = payload.is_active
    await db.commit()
    await db.refresh(automation)
    return automation_read(automation)


async def delete_automation(db: AsyncSession, automation: Automation) -> None:
    await db.delete(automation)
    await db.commit()


async def sweep_automations(db: AsyncSession, *, limit: int = 100) -> int:
    """Apply every due automation. Returns the number of applications."""
    now = utcnow()
    automations = (
        await db.execute(
            select(Automation)
            .where(Automation.is_active.is_(True))
            .order_by(Automation.position, Automation.created_at)
        )
    ).scalars().all()

    applied = 0
    for automation in automations:
        threshold = now - timedelta(minutes=max(0, automation.after_minutes))
        already = select(TicketAutomation.ticket_id).where(
            TicketAutomation.automation_id == automation.id
        )
        candidates = (
            await db.execute(
                select(Ticket)
                .where(
                    Ticket.workspace_id == automation.workspace_id,
                    Ticket.status.in_(OPEN_STATUSES),
                    Ticket.created_at <= threshold,
                    ~Ticket.id.in_(already),
                )
                .order_by(Ticket.created_at)
                .limit(limit)
            )
        ).scalars().all()
        for ticket in candidates:
            if not triggers_svc._matches(ticket, automation.conditions):
                continue
            changes = triggers_svc._apply_actions(ticket, automation.actions)
            changes += await triggers_svc.apply_notify_actions(
                db, ticket, automation.actions, source=f"automation:{automation.name}"
            )
            db.add(TicketAutomation(ticket_id=ticket.id, automation_id=automation.id))
            await tickets_svc.record_event(
                db,
                ticket=ticket,
                type="automation.applied",
                actor_type="system",
                data={"automation": automation.name, "changes": changes},
            )
            applied += 1
    if applied:
        await db.commit()
    return applied
