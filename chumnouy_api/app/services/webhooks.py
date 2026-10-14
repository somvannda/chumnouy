"""Outbound webhooks: registration, signed delivery and a retry ledger.

A ticket event fans out to one :class:`WebhookDelivery` row per active webhook
that subscribes to it. Delivery is signed with the webhook's secret
(``X-Chumnouy-Signature: sha256=<hmac(secret, f"{timestamp}.{body}")>``) so a
receiver can verify authenticity, and ``X-Chumnouy-Delivery`` carries a stable
event id so a replay can be de-duplicated. Failed attempts retry with backoff
until ``webhook_max_attempts`` is reached, then the delivery is ``failed``.

Chumnouy owns the event; Notifyr owns human-facing delivery (docs/architecture.md).
Webhooks here are machine-to-machine.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
from datetime import timedelta
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Ticket, Webhook, WebhookDelivery, utcnow
from app.schemas import WebhookDeliveryRead, WebhookRead

logger = logging.getLogger(__name__)

# Events a workspace can subscribe to.
EVENTS: frozenset[str] = frozenset(
    {
        "ticket.created",
        "ticket.replied",
        "ticket.status_changed",
        "ticket.assigned",
        "ticket.resolved",
        "ticket.reopened",
    }
)

# Delay before the next attempt, in seconds; index is ``attempts - 1`` (clamped).
BACKOFF_SECONDS: tuple[int, ...] = (10, 60, 300, 1800)


def generate_secret() -> str:
    return f"whsec_{secrets.token_hex(24)}"


def normalise_events(events: list[str] | None) -> list[str]:
    """Keep only known events, de-duplicated and stably ordered."""
    seen: list[str] = []
    for event in events or []:
        if event in EVENTS and event not in seen:
            seen.append(event)
    return seen


def webhook_read(webhook: Webhook) -> WebhookRead:
    return WebhookRead(
        id=webhook.id,
        url=webhook.url,
        description=webhook.description,
        events=list(webhook.events or []),
        is_active=webhook.is_active,
        created_at=webhook.created_at,
    )


def delivery_read(delivery: WebhookDelivery) -> WebhookDeliveryRead:
    return WebhookDeliveryRead(
        id=delivery.id,
        webhook_id=delivery.webhook_id,
        event=delivery.event,
        status=delivery.status,
        attempts=delivery.attempts,
        response_status=delivery.response_status,
        error=delivery.error,
        created_at=delivery.created_at,
        delivered_at=delivery.delivered_at,
    )


def sign(secret: str, timestamp: int, body: bytes) -> str:
    """HMAC-SHA256 over ``"<timestamp>.<body>"``, hex-encoded with a scheme prefix."""
    message = f"{timestamp}.".encode() + body
    return "sha256=" + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def _payload(ticket: Ticket, event: str, data: dict | None) -> dict:
    return {
        "event": event,
        "ticket": {
            "id": str(ticket.id),
            "reference": ticket.reference,
            "subject": ticket.subject,
            "status": ticket.status,
            "priority": ticket.priority,
        },
        "data": data or {},
    }


async def enqueue_event(
    db: AsyncSession, *, ticket: Ticket, event: str, data: dict | None = None
) -> list[WebhookDelivery]:
    """Queue one delivery per active webhook subscribed to ``event``.

    Adds rows to the caller's transaction (no commit), so a ticket write and its
    queued deliveries land atomically.
    """
    hooks = (
        await db.execute(
            select(Webhook).where(
                Webhook.workspace_id == ticket.workspace_id,
                Webhook.is_active.is_(True),
            )
        )
    ).scalars().all()
    payload = _payload(ticket, event, data)
    queued: list[WebhookDelivery] = []
    for hook in hooks:
        if event not in (hook.events or []):
            continue
        delivery = WebhookDelivery(
            webhook_id=hook.id,
            workspace_id=ticket.workspace_id,
            event=event,
            event_id=str(uuid4()),
            payload=payload,
            status="pending",
            attempts=0,
            next_attempt_at=utcnow(),
        )
        db.add(delivery)
        queued.append(delivery)
    return queued


async def _post(
    client: httpx.AsyncClient, webhook: Webhook, delivery: WebhookDelivery
) -> tuple[bool, int | None, str | None]:
    body = json.dumps(delivery.payload, separators=(",", ":"), default=str).encode()
    timestamp = int(utcnow().timestamp())
    headers = {
        "Content-Type": "application/json",
        "X-Chumnouy-Event": delivery.event,
        "X-Chumnouy-Delivery": delivery.event_id,
        "X-Chumnouy-Timestamp": str(timestamp),
        "X-Chumnouy-Signature": sign(webhook.secret, timestamp, body),
    }
    try:
        response = await client.post(webhook.url, content=body, headers=headers)
    except httpx.HTTPError as exc:
        return False, None, str(exc)
    text = (response.text or "")[:2000] or None
    return 200 <= response.status_code < 300, response.status_code, text


async def attempt_delivery(
    db: AsyncSession,
    delivery: WebhookDelivery,
    *,
    client: httpx.AsyncClient | None = None,
) -> WebhookDelivery:
    """Send one delivery and record the outcome, scheduling a retry on failure."""
    webhook = await db.get(Webhook, delivery.webhook_id)
    if webhook is None:
        delivery.status = "failed"
        delivery.error = "Webhook no longer exists"
        delivery.next_attempt_at = None
        await db.commit()
        return delivery

    delivery.attempts += 1
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.webhook_timeout_seconds)
    try:
        ok, status_code, body = await _post(client, webhook, delivery)
    finally:
        if owns_client:
            await client.aclose()

    now = utcnow()
    delivery.response_status = status_code
    delivery.response_body = body
    if ok:
        delivery.status = "delivered"
        delivery.delivered_at = now
        delivery.next_attempt_at = None
        delivery.error = None
    else:
        delivery.error = f"HTTP {status_code}" if status_code else (body or "request failed")
        if delivery.attempts >= settings.webhook_max_attempts:
            delivery.status = "failed"
            delivery.next_attempt_at = None
        else:
            index = min(delivery.attempts - 1, len(BACKOFF_SECONDS) - 1)
            delivery.status = "pending"
            delivery.next_attempt_at = now + timedelta(seconds=BACKOFF_SECONDS[index])
    await db.commit()
    await db.refresh(delivery)
    return delivery


async def process_due(
    db: AsyncSession, *, limit: int = 50, client: httpx.AsyncClient | None = None
) -> int:
    """Send every pending delivery whose next attempt is due. Returns the count."""
    now = utcnow()
    rows = (
        await db.execute(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.status == "pending",
                WebhookDelivery.next_attempt_at.is_not(None),
                WebhookDelivery.next_attempt_at <= now,
            )
            .order_by(WebhookDelivery.next_attempt_at)
            .limit(limit)
        )
    ).scalars().all()
    for delivery in rows:
        await attempt_delivery(db, delivery, client=client)
    return len(rows)


async def replay_delivery(db: AsyncSession, delivery: WebhookDelivery) -> WebhookDelivery:
    """Reset a delivery to pending so the worker sends it again."""
    delivery.status = "pending"
    delivery.attempts = 0
    delivery.response_status = None
    delivery.response_body = None
    delivery.error = None
    delivery.delivered_at = None
    delivery.next_attempt_at = utcnow()
    await db.commit()
    await db.refresh(delivery)
    return delivery


async def run_worker(stop: asyncio.Event) -> None:
    """Drain due webhook deliveries and Notifyr hand-offs until ``stop`` is set."""
    from app.db import SessionLocal
    from app.services import notifyr as notifyr_svc

    interval = max(1, settings.webhook_worker_interval_seconds)
    while not stop.is_set():
        try:
            async with SessionLocal() as session:
                await process_due(session)
                await notifyr_svc.process_due(session)
        except Exception:  # noqa: BLE001 - the worker must never die
            logger.exception("webhook worker iteration failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
