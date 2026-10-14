"""Notifyr hand-off: raise ticket events to the Notifyr API.

Chumnouy owns the ticket event; Notifyr owns human-facing delivery (email/SMS/
Telegram, preferences and retries). We POST a small event and never send mail
ourselves (docs/architecture.md product boundary). Delivery is best-effort by
design: a ticket write must never fail because Notifyr was unreachable or the
hand-off was unconfigured.
"""
from __future__ import annotations

import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Ticket, Workspace

logger = logging.getLogger(__name__)

TICKET_CREATED = "ticket.created"
TICKET_REPLIED = "ticket.replied"


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
    event: str, workspace: Workspace, ticket: Ticket, recipient: str | None, variables: dict | None
) -> dict:
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
        "variables": variables or {},
    }


async def send_event(
    *,
    event: str,
    workspace: Workspace,
    ticket: Ticket,
    recipient: str | None = None,
    variables: dict | None = None,
    client: httpx.AsyncClient | None = None,
) -> bool:
    """POST one event to Notifyr. Returns whether it was accepted. Never raises."""
    url, key = load_notifyr_settings(workspace)
    if not (url and key):
        return False
    headers = {
        "Authorization": f"Bearer {key}",
        "content-type": "application/json",
    }
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.webhook_timeout_seconds)
    try:
        response = await client.post(
            _endpoint(url),
            headers=headers,
            json=_payload(event, workspace, ticket, recipient, variables),
        )
        if response.status_code >= 400:
            logger.warning("Notifyr rejected %s: HTTP %s", event, response.status_code)
            return False
        return True
    except httpx.HTTPError as exc:
        logger.warning("Notifyr unreachable for %s: %s", event, exc)
        return False
    finally:
        if owns_client:
            await client.aclose()


async def notify_ticket_event(
    db: AsyncSession,
    *,
    workspace: Workspace,
    ticket: Ticket,
    event: str,
    recipient: str | None = None,
    variables: dict | None = None,
    client: httpx.AsyncClient | None = None,
) -> bool:
    """Best-effort hand-off. Swallows everything so a ticket write never fails.

    ``recipient`` is passed by the caller: a requester email when the workspace's
    agents are being notified of a reply, or ``None`` to let Notifyr resolve the
    workspace's agent recipients.
    """
    try:
        if not is_configured(workspace):
            return False
        return await send_event(
            event=event,
            workspace=workspace,
            ticket=ticket,
            recipient=recipient,
            variables=variables,
            client=client,
        )
    except Exception:  # noqa: BLE001 - the hand-off must never break a write
        logger.exception("Notifyr hand-off failed for %s", event)
        return False
