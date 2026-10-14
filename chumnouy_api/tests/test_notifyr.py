"""Notifyr outbox: queue on ticket events, hand off from the worker, no-op unconfigured."""
import json

import httpx
import pytest
from sqlalchemy import select

from app.config import settings
from app.models import NotifyrEvent
from app.services import notifyr as svc

pytestmark = pytest.mark.asyncio


async def _signup(client, *, email, workspace="Acme Support"):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
    )
    assert signup.status_code == 201, signup.text
    token = signup.json()["token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _key(client, headers, *, scopes=("tickets:read", "tickets:write")):
    integration = await client.post(
        "/api/v1/integrations", json={"name": "POS", "scopes": list(scopes)}, headers=headers
    )
    return (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]


def _configure(monkeypatch):
    monkeypatch.setattr(settings, "notifyr_api_url", "https://notifyr.test")
    monkeypatch.setattr(settings, "notifyr_api_key", "nkey_test")


def _ticket_body(email="dara@example.com"):
    return {
        "subject": "Card reader down",
        "message": "The terminal stopped charging.",
        "requester": {"external_id": "cust_1", "name": "Sok Dara", "email": email},
    }


async def _rows(db_session):
    db_session.expire_all()
    return (await db_session.execute(select(NotifyrEvent))).scalars().all()


async def test_unconfigured_enqueues_nothing(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "notifyr_api_url", "")
    monkeypatch.setattr(settings, "notifyr_api_key", "")
    _, headers = await _signup(client, email="unset@example.com")
    key = await _key(client, headers)

    await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})
    assert await _rows(db_session) == []


async def test_new_ticket_is_queued_for_agents(client, db_session, monkeypatch):
    _configure(monkeypatch)
    _, headers = await _signup(client, email="queue@example.com")
    key = await _key(client, headers)

    await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})

    rows = await _rows(db_session)
    assert len(rows) == 1
    assert rows[0].event == "ticket.created"
    assert rows[0].recipient is None  # Notifyr resolves the workspace's agents
    assert rows[0].status == "pending"


async def test_worker_hands_off_the_event(client, db_session, monkeypatch):
    _configure(monkeypatch)
    _, headers = await _signup(client, email="worker@example.com")
    key = await _key(client, headers)
    await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(202, text="accepted")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock:
        sent = await svc.process_due(db_session, client=mock)

    assert sent == 1
    request = captured[0]
    assert str(request.url) == "https://notifyr.test/v1/events"
    assert request.headers["authorization"] == "Bearer nkey_test"
    body = json.loads(request.content)
    assert body["event"] == "ticket.created"
    assert body["recipient"] is None
    assert body["ticket"]["reference"].startswith("CMY-")

    row = (await _rows(db_session))[0]
    assert row.status == "delivered"
    assert row.response_status == 202


async def test_agent_reply_targets_the_requester(client, db_session, monkeypatch):
    _configure(monkeypatch)
    _, headers = await _signup(client, email="reply@example.com")
    key = await _key(client, headers)
    ticket_id = (
        await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})
    ).json()["id"]

    await client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        json={"body": "We are on it.", "visibility": "public"},
        headers=headers,
    )

    replies = [row for row in await _rows(db_session) if row.event == "ticket.replied"]
    assert len(replies) == 1
    assert replies[0].recipient == "dara@example.com"


async def test_internal_note_is_not_queued(client, db_session, monkeypatch):
    _configure(monkeypatch)
    _, headers = await _signup(client, email="internal@example.com")
    key = await _key(client, headers)
    ticket_id = (
        await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})
    ).json()["id"]

    await client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        json={"body": "Internal only.", "visibility": "internal"},
        headers=headers,
    )

    assert [row.event for row in await _rows(db_session)] == ["ticket.created"]


async def test_failed_hand_off_schedules_a_retry(client, db_session, monkeypatch):
    _configure(monkeypatch)
    _, headers = await _signup(client, email="retry@example.com")
    key = await _key(client, headers)
    await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock:
        await svc.process_due(db_session, client=mock)

    row = (await _rows(db_session))[0]
    assert row.status == "pending"
    assert row.attempts == 1
    assert row.response_status == 500
    assert row.next_attempt_at is not None


async def test_terminal_failure_after_max_attempts(client, db_session, monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "webhook_max_attempts", 1)
    _, headers = await _signup(client, email="fail@example.com")
    key = await _key(client, headers)
    await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock:
        await svc.process_due(db_session, client=mock)

    row = (await _rows(db_session))[0]
    assert row.status == "failed"
    assert row.attempts == 1
    assert row.next_attempt_at is None
