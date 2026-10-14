"""Webhooks: registration, signed delivery, retry/backoff and replay.

Delivery is exercised through ``process_due`` with an ``httpx.MockTransport``
client so no real network calls happen, and the HMAC signature is recomputed
from the stored secret to prove the receiver could verify it.
"""
import httpx
import pytest

from app.config import settings
from app.services import webhooks as svc

pytestmark = pytest.mark.asyncio


async def _workspace(client, *, email, workspace="Acme Support"):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
    )
    assert signup.status_code == 201, signup.text
    token = signup.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    integration = await client.post(
        "/api/v1/integrations",
        json={"name": "Chmaba POS", "scopes": ["tickets:read", "tickets:write"]},
        headers=headers,
    )
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys",
            json={"name": "k", "environment": "live"},
            headers=headers,
        )
    ).json()["key"]
    return token, key


async def _webhook(client, token, *, events, url="https://example.com/hook"):
    resp = await client.post(
        "/api/v1/webhooks",
        json={"url": url, "events": events},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _ticket_body(subject="Card reader down"):
    return {
        "subject": subject,
        "message": "The terminal stopped charging.",
        "requester": {"external_id": "cust_1", "email": "dara@example.com"},
    }


class _Recorder:
    def __init__(self, status_code=200):
        self.requests: list[httpx.Request] = []
        self.status_code = status_code

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status_code, text="ok")


def _client(recorder: _Recorder) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(recorder.handler))


async def test_create_returns_secret_once_and_filters_events(client, db_session):
    token, _ = await _workspace(client, email="wh@example.com")
    created = await _webhook(client, token, events=["ticket.created", "bogus.event", "ticket.created"])
    assert created["secret"].startswith("whsec_")
    assert created["webhook"]["events"] == ["ticket.created"]

    listed = await client.get("/api/v1/webhooks", headers={"Authorization": f"Bearer {token}"})
    assert listed.status_code == 200
    assert listed.json()[0]["events"] == ["ticket.created"]
    assert "secret" not in listed.json()[0]


async def test_ticket_event_is_delivered_with_a_valid_signature(client, db_session):
    token, key = await _workspace(client, email="sig@example.com")
    created = await _webhook(client, token, events=["ticket.created"])
    secret = created["secret"]
    webhook_id = created["webhook"]["id"]

    await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})

    recorder = _Recorder()
    async with _client(recorder) as mock:
        count = await svc.process_due(db_session, client=mock)
    assert count == 1
    assert len(recorder.requests) == 1

    request = recorder.requests[0]
    timestamp = int(request.headers["X-Chumnouy-Timestamp"])
    assert request.headers["X-Chumnouy-Event"] == "ticket.created"
    assert request.headers["X-Chumnouy-Delivery"]
    assert request.headers["X-Chumnouy-Signature"] == svc.sign(secret, timestamp, request.content)

    log = await client.get(
        f"/api/v1/webhooks/{webhook_id}/deliveries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert log.status_code == 200
    assert log.json()[0]["status"] == "delivered"


async def test_failed_delivery_schedules_a_retry(client, db_session):
    token, key = await _workspace(client, email="retry@example.com")
    created = await _webhook(client, token, events=["ticket.created"])
    await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})

    recorder = _Recorder(status_code=500)
    async with _client(recorder) as mock:
        await svc.process_due(db_session, client=mock)

    log = await client.get(
        f"/api/v1/webhooks/{created['webhook']['id']}/deliveries",
        headers={"Authorization": f"Bearer {token}"},
    )
    delivery = log.json()[0]
    assert delivery["status"] == "pending"
    assert delivery["attempts"] == 1
    assert delivery["response_status"] == 500


async def test_terminal_failure_after_max_attempts(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "webhook_max_attempts", 1)
    token, key = await _workspace(client, email="fail@example.com")
    created = await _webhook(client, token, events=["ticket.created"])
    await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})

    recorder = _Recorder(status_code=500)
    async with _client(recorder) as mock:
        await svc.process_due(db_session, client=mock)

    log = await client.get(
        f"/api/v1/webhooks/{created['webhook']['id']}/deliveries",
        headers={"Authorization": f"Bearer {token}"},
    )
    delivery = log.json()[0]
    assert delivery["status"] == "failed"
    assert delivery["attempts"] == 1


async def test_replay_requeues_a_delivery(client, db_session):
    token, key = await _workspace(client, email="replay@example.com")
    created = await _webhook(client, token, events=["ticket.created"])
    await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})
    headers = {"Authorization": f"Bearer {token}"}

    recorder = _Recorder(status_code=500)
    async with _client(recorder) as mock:
        await svc.process_due(db_session, client=mock)

    delivery_id = (
        await client.get(f"/api/v1/webhooks/{created['webhook']['id']}/deliveries", headers=headers)
    ).json()[0]["id"]

    replayed = await client.post(f"/api/v1/webhooks/deliveries/{delivery_id}/replay", headers=headers)
    assert replayed.status_code == 200, replayed.text
    assert replayed.json()["status"] == "pending"
    assert replayed.json()["attempts"] == 0

    ok = _Recorder()
    async with _client(ok) as mock:
        await svc.process_due(db_session, client=mock)
    assert len(ok.requests) == 1


async def test_webhooks_are_workspace_isolated(client, db_session):
    _, key_a = await _workspace(client, email="a@example.com", workspace="Workspace A")
    token_b, key_b = await _workspace(client, email="b@example.com", workspace="Workspace B")
    created_b = await _webhook(client, token_b, events=["ticket.created"])

    # A ticket in workspace A must not reach workspace B's webhook.
    await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key_a})

    recorder = _Recorder()
    async with _client(recorder) as mock:
        count = await svc.process_due(db_session, client=mock)
    assert count == 0
    assert recorder.requests == []

    log = await client.get(
        f"/api/v1/webhooks/{created_b['webhook']['id']}/deliveries",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert log.json() == []


async def test_webhooks_require_manage_scope(client):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": "scope@example.com", "password": "supersecret123", "name": "Owner"},
    )
    token = signup.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    integration = await client.post(
        "/api/v1/integrations", json={"name": "Reader", "scopes": ["tickets:read"]}, headers=headers
    )
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]

    denied = await client.post(
        "/api/v1/webhooks",
        json={"url": "https://example.com/hook", "events": ["ticket.created"]},
        headers={"X-Api-Key": key},
    )
    assert denied.status_code == 403

    allowed = await client.get("/api/v1/webhooks", headers=headers)
    assert allowed.status_code == 200


async def test_delete_webhook(client):
    token, _ = await _workspace(client, email="delete@example.com")
    created = await _webhook(client, token, events=["ticket.created"])
    headers = {"Authorization": f"Bearer {token}"}

    deleted = await client.delete(f"/api/v1/webhooks/{created['webhook']['id']}", headers=headers)
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/webhooks", headers=headers)).json() == []
    missing = await client.get(
        f"/api/v1/webhooks/{created['webhook']['id']}/deliveries", headers=headers
    )
    assert missing.status_code == 404
