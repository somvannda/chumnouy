"""Notifyr hand-off: signed-off payload, best-effort behaviour, ticket hooks."""
import json
import uuid
from types import SimpleNamespace

import httpx
import pytest

from app.config import settings
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


def _recorder(monkeypatch):
    calls: list[dict] = []

    async def fake_send(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(svc, "send_event", fake_send)
    return calls


def _ticket_body(email="dara@example.com"):
    return {
        "subject": "Card reader down",
        "message": "The terminal stopped charging.",
        "requester": {"external_id": "cust_1", "name": "Sok Dara", "email": email},
    }


async def test_send_event_posts_the_expected_payload(monkeypatch):
    _configure(monkeypatch)
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(202, text="accepted")

    workspace = SimpleNamespace(id=uuid.uuid4(), slug="acme")
    ticket = SimpleNamespace(
        id=uuid.uuid4(), reference="CMY-1", subject="Hi", status="open", priority="normal"
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        ok = await svc.send_event(
            event="ticket.created",
            workspace=workspace,
            ticket=ticket,
            recipient="dara@example.com",
            client=client,
        )

    assert ok is True
    request = captured[0]
    assert str(request.url) == "https://notifyr.test/v1/events"
    assert request.headers["authorization"] == "Bearer nkey_test"
    body = json.loads(request.content)
    assert body["event"] == "ticket.created"
    assert body["workspace"]["slug"] == "acme"
    assert body["ticket"]["reference"] == "CMY-1"
    assert body["recipient"] == "dara@example.com"


async def test_unconfigured_hand_off_is_a_noop(monkeypatch):
    monkeypatch.setattr(settings, "notifyr_api_url", "")
    monkeypatch.setattr(settings, "notifyr_api_key", "")
    calls = _recorder(monkeypatch)
    ticket = SimpleNamespace(requester_id=None)
    workspace = SimpleNamespace(id=uuid.uuid4(), slug="acme")
    assert await svc.notify_ticket_event(None, workspace=workspace, ticket=ticket, event="x") is False
    assert calls == []


async def test_new_ticket_notifies_agents(client, monkeypatch):
    _, headers = await _signup(client, email="agent@example.com")
    key = await _key(client, headers)
    _configure(monkeypatch)
    calls = _recorder(monkeypatch)

    resp = await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})
    assert resp.status_code == 201, resp.text
    assert len(calls) == 1
    assert calls[0]["event"] == "ticket.created"
    assert calls[0]["recipient"] is None  # Notifyr resolves the workspace's agents


async def test_agent_reply_notifies_the_requester(client, monkeypatch):
    _, headers = await _signup(client, email="agent2@example.com")
    key = await _key(client, headers)
    _configure(monkeypatch)
    calls = _recorder(monkeypatch)
    ticket_id = (await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})).json()["id"]
    calls.clear()

    await client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        json={"body": "We are on it.", "visibility": "public"},
        headers=headers,
    )
    assert [c["event"] for c in calls] == ["ticket.replied"]
    assert calls[0]["recipient"] == "dara@example.com"


async def test_internal_notes_are_not_forwarded(client, monkeypatch):
    _, headers = await _signup(client, email="agent3@example.com")
    key = await _key(client, headers)
    _configure(monkeypatch)
    calls = _recorder(monkeypatch)
    ticket_id = (await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})).json()["id"]
    calls.clear()

    await client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        json={"body": "Internal only.", "visibility": "internal"},
        headers=headers,
    )
    assert calls == []
