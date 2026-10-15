"""Notifyr hand-off: queue ticket events for human-facing delivery.

Chumnouy owns the ticket event; Notifyr owns delivery (docs/architecture.md
product boundary). Events are enqueued inside the ticket transaction
(``notifyr_events``) and handed off by a worker with retry/backoff, so a ticket
write never blocks on — or fails because of — Notifyr. Unconfigured workspaces
enqueue nothing.
"""
from __future__ import annotations

import logging
from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import NotifyrEvent, Ticket, Workspace, utcnow

logger = logging.getLogger(__name__)

TICKET_CREATED = "ticket.created"
TICKET_REPLIED = "ticket.replied"
TICKET_MENTIONED = "ticket.mentioned"

BACKOFF_SECONDS: tuple[int, ...] = (10, 60, 300, 1800)


def load_notifyr_settings(workspace: Workspace) -> tuple[str, str]:
    """Effective Notifyr url + key: a workspace override, else the env defaults."""
    stored = getattr(workspace, "settings", None) or {}
    url = (stored.get("notifyr_api_url") or settings.notifyr_api_url or "").strip()
    key = (stored.get("notifyr_api_key") or settings.notifyr_api_key or "").strip()
    return url, key


def is_configured(workspace: Workspace) -> bool:
    url, key = load_notifyr_settings(workspace)
    return bool(url and key)


def _endpoint(url: str) -> str:
    return f"{url.rstrip('/')}/v1/events"


def _payload(
    event: str,
    workspace: Workspace,
    ticket: Ticket,
    recipient: str | None,
    variables: dict | None,
) -> dict:
    # Notifyr renders the message; it needs the workspace locale for templates.
    merged = {"locale": (workspace.settings or {}).get("locale") or "en"}
    merged.update(variables or {})
    return {
        "event": event,
        "workspace": {"id": str(workspace.id), "slug": workspace.slug},
        "ticket": {
            "id": str(ticket.id),
            "reference": ticket.reference,
            "subject": ticket.subject,
            "status": ticket.status,
            "priority": ticket.priority,
        },
        "recipient": recipient,
        "variables": merged,
    }


async def enqueue(
    db: AsyncSession,
    *,
    workspace: Workspace,
    ticket: Ticket,
    event: str,
    recipient: str | None = None,
    variables: dict | None = None,
) -> NotifyrEvent | None:
    """Queue a hand-off in the caller's transaction. No-op when unconfigured."""
    if not is_configured(workspace):
        return None
    record = NotifyrEvent(
        workspace_id=workspace.id,
        ticket_id=ticket.id,
        event=event,
        recipient=recipient,
        payload=_payload(event, workspace, ticket, recipient, variables),
        status="pending",
        attempts=0,
        next_attempt_at=utcnow(),
    )
    db.add(record)
    return record


async def send_event(
    *,
    workspace: Workspace,
    payload: dict,
    client: httpx.AsyncClient | None = None,
) -> tuple[bool, int | None, str | None]:
    """POST one payload to Notifyr. Returns ``(ok, status, error)``. Never raises."""
    url, key = load_notifyr_settings(workspace)
    if not (url and key):
        return False, None, "Notifyr is not configured"
    headers = {"Authorization": f"Bearer {key}", "content-type": "application/json"}
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.webhook_timeout_seconds)
    try:
        response = await client.post(_endpoint(url), headers=headers, json=payload)
    except httpx.HTTPError as exc:
        return False, None, str(exc)
    finally:
        if owns_client:
            await client.aclose()
    if response.status_code >= 400:
        return False, response.status_code, f"HTTP {response.status_code}"
    return True, response.status_code, None


async def deliver(
    db: AsyncSession, record: NotifyrEvent, *, client: httpx.AsyncClient | None = None
) -> NotifyrEvent:
    """Hand one queued event to Notifyr and record the outcome, retrying on failure."""
    workspace = await db.get(Workspace, record.workspace_id)
    if workspace is None:
        record.status = "failed"
        record.error = "Workspace no longer exists"
        record.next_attempt_at = None
        await db.commit()
        return record

    record.attempts += 1
    ok, status, error = await send_event(workspace=workspace, payload=record.payload, client=client)
    now = utcnow()
    record.response_status = status
    if ok:
        record.status = "delivered"
        record.delivered_at = now
        record.error = None
        record.next_attempt_at = None
    else:
        record.error = error
        if record.attempts >= settings.webhook_max_attempts:
            record.status = "failed"
            record.next_attempt_at = None
        else:
            index = min(record.attempts - 1, len(BACKOFF_SECONDS) - 1)
            record.status = "pending"
            record.next_attempt_at = now + timedelta(seconds=BACKOFF_SECONDS[index])
    await db.commit()
    await db.refresh(record)
    return record


async def process_due(
    db: AsyncSession, *, limit: int = 50, client: httpx.AsyncClient | None = None
) -> int:
    """Hand off every due queued event. Returns the count processed."""
    now = utcnow()
    rows = (
        await db.execute(
            select(NotifyrEvent)
            .where(
                NotifyrEvent.status == "pending",
                NotifyrEvent.next_attempt_at.is_not(None),
                NotifyrEvent.next_attempt_at <= now,
            )
            .order_by(NotifyrEvent.next_attempt_at)
            .limit(limit)
        )
    ).scalars().all()
    for record in rows:
        await deliver(db, record, client=client)
    return len(rows)
