"""End-to-end: the whole support journey through one API flow.

Not a substitute for the focused tests, but it proves the pieces compose —
signup → seeded corpus → integration + key → webhook → ticket (idempotent) →
reply (idempotent) → resolve → signed delivery → requester portal → admin usage.
"""
import json

import httpx
import pytest
from sqlalchemy import select

from app.config import settings
from app.models import User
from app.services import webhooks as webhook_svc

pytestmark = pytest.mark.asyncio


def _ticket_body():
    return {
        "subject": "Card reader not charging",
        "message": "The terminal stopped charging this morning.",
        "requester": {"external_id": "cust_9", "name": "Sok Dara", "email": "dara@example.com"},
        "priority": "high",
    }


async def test_full_support_journey(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "notifyr_api_url", "")
    monkeypatch.setattr(settings, "notifyr_api_key", "")

    # 1. Signup creates a workspace and seeds the help corpus.
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "journey@example.com",
            "password": "supersecret123",
            "name": "Owner",
            "workspace_name": "Journey Support",
        },
    )
    assert signup.status_code == 201, signup.text
    token = signup.json()["token"]
    console = {"Authorization": f"Bearer {token}"}
    corpus = await client.get("/api/v1/knowledge/articles", headers=console)
    assert corpus.status_code == 200 and corpus.json()

    # 2. Register an integration and take a scoped key.
    integration = await client.post(
        "/api/v1/integrations",
        json={"name": "Chmaba POS", "scopes": ["tickets:read", "tickets:write", "requesters:write"]},
        headers=console,
    )
    assert integration.status_code == 201, integration.text
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys",
            json={"name": "live", "environment": "live"},
            headers=console,
        )
    ).json()["key"]
    machine = {"X-Api-Key": key}

    # 3. Subscribe a webhook.
    hook = await client.post(
        "/api/v1/webhooks",
        json={"url": "https://example.com/hook", "events": ["ticket.created", "ticket.replied"]},
        headers=console,
    )
    assert hook.status_code == 201, hook.text
    secret = hook.json()["secret"]

    # 4. Open a ticket idempotently.
    idem_create = {**machine, "Idempotency-Key": "journey-create"}
    created = await client.post("/api/v1/tickets", json=_ticket_body(), headers=idem_create)
    again = await client.post("/api/v1/tickets", json=_ticket_body(), headers=idem_create)
    assert created.status_code == 201, created.text
    assert created.json()["id"] == again.json()["id"]
    ticket_id = created.json()["id"]

    # 5. An agent replies (idempotently) and resolves.
    idem_reply = {**console, "Idempotency-Key": "journey-reply"}
    reply = await client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        json={"body": "Please reseat the cable.", "visibility": "public"},
        headers=idem_reply,
    )
    repeat = await client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        json={"body": "Please reseat the cable.", "visibility": "public"},
        headers=idem_reply,
    )
    assert reply.status_code == 201 and reply.json()["id"] == repeat.json()["id"]
    resolved = await client.post(f"/api/v1/tickets/{ticket_id}/resolve", headers=console)
    assert resolved.json()["status"] == "resolved"

    # 6. Deliver the queued webhooks, signed.
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, text="ok")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock:
        sent = await webhook_svc.process_due(db_session, client=mock)
    assert sent == 2  # ticket.created + ticket.replied
    request = captured[0]
    timestamp = int(request.headers["X-Chumnouy-Timestamp"])
    assert request.headers["X-Chumnouy-Signature"] == webhook_svc.sign(
        secret, timestamp, request.content
    )
    assert json.loads(request.content)["ticket"]["reference"].startswith("CMY-")

    # 7. The requester portal sees only public messages.
    requester = (await client.get("/api/v1/requesters?q=cust_9", headers=console)).json()[0]
    portal_token = (
        await client.post(f"/api/v1/requesters/{requester['id']}/portal-token", headers=console)
    ).json()["token"]
    await client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        json={"body": "Internal note", "visibility": "internal"},
        headers=console,
    )
    portal = {"X-Requester-Token": portal_token}
    mine = await client.get(f"/api/v1/public/tickets/{ticket_id}", headers=portal)
    assert mine.status_code == 200
    assert "Internal note" not in [m["body"] for m in mine.json()["messages"]]

    # 8. Platform admin sees the workspace in usage.
    user = (await db_session.execute(select(User).where(User.email == "journey@example.com"))).scalar_one()
    user.platform_role = "admin"
    await db_session.commit()
    usage = await client.get("/api/admin/usage", headers=console)
    assert usage.status_code == 200, usage.text
    assert usage.json()["tickets"] == 1
