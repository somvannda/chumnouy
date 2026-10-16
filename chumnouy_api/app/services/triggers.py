"""Event-based triggers.

A trigger is a rule: when ``event`` fires for a ticket and its ``conditions``
match, its ``actions`` run against that ticket. Triggers are evaluated once per
ticket write, in ``position`` order; their actions do not re-trigger.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ticket, Trigger, Webhook, Workspace
from app.schemas import TriggerCreate, TriggerRead, TriggerUpdate
from app.services import notifyr as notifyr_svc
from app.services import webhooks as webhooks_svc

TRIGGER_EVENTS = ("ticket.created", "ticket.replied", "ticket.updated")
VALID_STATUSES = ("open", "pending", "resolved", "closed")
VALID_PRIORITIES = ("low", "normal", "high", "urgent")
# The event name used for deliveries queued by a ``webhook`` action.
WEBHOOK_ACTION_EVENT = "action.webhook"


def trigger_read(trigger: Trigger) -> TriggerRead:
    return TriggerRead(
        id=trigger.id,
        name=trigger.name,
        event=trigger.event,
        conditions=list(trigger.conditions or []),
        actions=list(trigger.actions or []),
        position=trigger.position,
        is_active=trigger.is_active,
        created_at=trigger.created_at,
        updated_at=trigger.updated_at,
    )


async def list_triggers(db: AsyncSession, workspace_id: UUID) -> list[TriggerRead]:
    rows = (
        await db.execute(
            select(Trigger)
            .where(Trigger.workspace_id == workspace_id)
            .order_by(Trigger.position, Trigger.created_at)
        )
    ).scalars().all()
    return [trigger_read(row) for row in rows]


async def load_trigger(db: AsyncSession, workspace_id: UUID, trigger_id: UUID) -> Trigger | None:
    return (
        await db.execute(
            select(Trigger).where(Trigger.id == trigger_id, Trigger.workspace_id == workspace_id)
        )
    ).scalar_one_or_none()


async def create_trigger(
    db: AsyncSession, workspace_id: UUID, payload: TriggerCreate
) -> TriggerRead:
    trigger = Trigger(
        workspace_id=workspace_id,
        name=payload.name.strip(),
        event=payload.event,
        conditions=[c.model_dump() for c in payload.conditions],
        actions=[a.model_dump() for a in payload.actions],
        position=payload.position,
        is_active=payload.is_active,
    )
    db.add(trigger)
    await db.commit()
    await db.refresh(trigger)
    return trigger_read(trigger)


async def update_trigger(
    db: AsyncSession, trigger: Trigger, payload: TriggerUpdate
) -> TriggerRead:
    if payload.name is not None:
        trigger.name = payload.name.strip()
    if payload.event is not None:
        trigger.event = payload.event
    if payload.conditions is not None:
        trigger.conditions = [c.model_dump() for c in payload.conditions]
    if payload.actions is not None:
        trigger.actions = [a.model_dump() for a in payload.actions]
    if payload.position is not None:
        trigger.position = payload.position
    if payload.is_active is not None:
        trigger.is_active = payload.is_active
    await db.commit()
    await db.refresh(trigger)
    return trigger_read(trigger)


async def delete_trigger(db: AsyncSession, trigger: Trigger) -> None:
    await db.delete(trigger)
    await db.commit()


def _matches(ticket: Ticket, conditions: list[dict]) -> bool:
    for condition in conditions or []:
        field = condition.get("field")
        op = condition.get("op", "is")
        value = str(condition.get("value", ""))
        if field == "status" and ticket.status != value:
            return False
        if field == "priority" and ticket.priority != value:
            return False
        if field == "tag" and value not in (ticket.tags or []):
            return False
        if field == "subject":
            if op == "contains" and value.lower() not in (ticket.subject or "").lower():
                return False
            if op == "is" and (ticket.subject or "") != value:
                return False
    return True


def _apply_actions(ticket: Ticket, actions: list[dict]) -> list[str]:
    applied: list[str] = []
    for action in actions or []:
        kind = action.get("type")
        value = action.get("value")
        if kind == "set_status" and value in VALID_STATUSES:
            ticket.status = value
            applied.append(f"status={value}")
        elif kind == "set_priority" and value in VALID_PRIORITIES:
            ticket.priority = value
            applied.append(f"priority={value}")
        elif kind == "add_tag" and value and value not in (ticket.tags or []):
            ticket.tags = [*(ticket.tags or []), value]
            applied.append(f"+tag:{value}")
        elif kind == "remove_tag" and value:
            ticket.tags = [tag for tag in (ticket.tags or []) if tag != value]
            applied.append(f"-tag:{value}")
        elif kind == "set_team" and value:
            try:
                ticket.team_id = UUID(str(value))
                applied.append(f"team={value}")
            except (ValueError, TypeError):
                pass
    return applied


async def apply_notify_actions(
    db: AsyncSession, ticket: Ticket, actions: list[dict], *, source: str
) -> list[str]:
    """Hand off ``notify`` actions to Notifyr. ``value`` is the recipient:
    ``requester`` (their email), ``agents`` (Notifyr resolves), or an email."""
    notify = [a for a in (actions or []) if a.get("type") == "notify"]
    if not notify:
        return []
    workspace = await db.get(Workspace, ticket.workspace_id)
    if workspace is None:
        return []
    from app.models import Requester  # local import avoids a cycle

    requester = None
    if ticket.requester_id is not None:
        requester = (
            await db.execute(select(Requester).where(Requester.id == ticket.requester_id))
        ).scalar_one_or_none()
    applied: list[str] = []
    for action in notify:
        value = str(action.get("value") or "agents").strip().lower()
        if value in ("requester", "customer") and requester:
            recipient = requester.email
        elif value in ("agents", "team", ""):
            recipient = None
        else:
            recipient = value
        await notifyr_svc.enqueue(
            db,
            workspace=workspace,
            ticket=ticket,
            event=notifyr_svc.TICKET_NOTIFIED,
            recipient=recipient,
            variables={"source": source},
        )
        applied.append(f"notify:{value}")
    return applied


async def apply_webhook_actions(
    db: AsyncSession, ticket: Ticket, actions: list[dict], *, source: str
) -> list[str]:
    """Run ``webhook`` actions: queue a delivery to the referenced workspace webhook.

    ``value`` is the id of a webhook configured for this workspace. Deliveries use
    the usual retry/backoff worker and delivery log, and carry ``source`` (the
    trigger/automation name) so the receiver can tell why it was called.
    """
    targets = [a for a in (actions or []) if a.get("type") == "webhook"]
    if not targets:
        return []
    applied: list[str] = []
    for action in targets:
        try:
            webhook_id = UUID(str(action.get("value")))
        except (TypeError, ValueError):
            continue
        hook = (
            await db.execute(
                select(Webhook).where(
                    Webhook.id == webhook_id,
                    Webhook.workspace_id == ticket.workspace_id,
                    Webhook.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if hook is None:
            continue
        await webhooks_svc.enqueue_delivery(
            db,
            ticket=ticket,
            webhook=hook,
            event=WEBHOOK_ACTION_EVENT,
            data={"source": source},
        )
        applied.append(f"webhook={hook.id}")
    return applied


async def apply_triggers(db: AsyncSession, *, ticket: Ticket, event: str) -> list[str]:
    """Run the workspace's active triggers for ``event`` against ``ticket``."""
    rows = (
        await db.execute(
            select(Trigger)
            .where(
                Trigger.workspace_id == ticket.workspace_id,
                Trigger.event == event,
                Trigger.is_active.is_(True),
            )
            .order_by(Trigger.position, Trigger.created_at)
        )
    ).scalars().all()
    applied: list[str] = []
    for trigger in rows:
        if not _matches(ticket, trigger.conditions):
            continue
        changes = _apply_actions(ticket, trigger.actions)
        changes += await apply_notify_actions(
            db, ticket, trigger.actions, source=f"trigger:{trigger.name}"
        )
        changes += await apply_webhook_actions(
            db, ticket, trigger.actions, source=f"trigger:{trigger.name}"
        )
        if changes:
            from app.services import tickets as tickets_svc  # local import avoids a cycle

            await tickets_svc.record_event(
                db,
                ticket=ticket,
                type="trigger.applied",
                actor_type="system",
                data={"trigger": trigger.name, "changes": changes},
            )
            applied.append(trigger.name)
    return applied
