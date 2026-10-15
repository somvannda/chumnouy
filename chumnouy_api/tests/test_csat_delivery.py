"""Resolving a ticket raises a CSAT prompt to Notifyr for the requester."""
import pytest
from sqlalchemy import select

from app.config import settings
from app.models import NotifyrEvent

pytestmark = pytest.mark.asyncio


async def _workspace(client, *, email):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": "Acme"},
    )
    assert signup.status_code == 201, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}
    integration = await client.post(
        "/api/v1/integrations",
        json={"name": "POS", "scopes": ["tickets:read", "tickets:write"]},
        headers=headers,
    )
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]
    return headers, key


async def test_resolve_queues_a_csat_hand_off(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "notifyr_api_url", "https://notifyr.test")
    monkeypatch.setattr(settings, "notifyr_api_key", "nkey")
    headers, key = await _workspace(client, email="csatd@example.com")
    ticket_id = (
        await client.post(
            "/api/v1/tickets",
            json={
                "subject": "Hi",
                "message": "hello",
                "requester": {"external_id": "c1", "email": "dara@example.com"},
            },
            headers={"X-Api-Key": key},
        )
    ).json()["id"]

    await client.post(f"/api/v1/tickets/{ticket_id}/resolve", headers=headers)

    db_session.expire_all()
    events = (await db_session.execute(select(NotifyrEvent))).scalars().all()
    resolved = [e for e in events if e.event == "ticket.resolved"]
    assert len(resolved) == 1
    assert resolved[0].recipient == "dara@example.com"
    assert resolved[0].payload["variables"]["csat"] is True
