"""Trigger/automation ``notify`` actions hand a ticket to Notifyr."""
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


async def _ticket(client, key, tags=None):
    return (
        await client.post(
            "/api/v1/tickets",
            json={
                "subject": "Hi",
                "message": "hello",
                "requester": {"external_id": "c1", "email": "dara@example.com"},
                "tags": tags or [],
            },
            headers={"X-Api-Key": key},
        )
    ).json()["id"]


async def test_trigger_notify_action(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "notifyr_api_url", "https://notifyr.test")
    monkeypatch.setattr(settings, "notifyr_api_key", "nkey")
    headers, key = await _workspace(client, email="notify-trigger@example.com")
    await client.post(
        "/api/v1/triggers",
        json={
            "name": "Tell the requester",
            "event": "ticket.created",
            "conditions": [{"field": "tag", "op": "is", "value": "vip"}],
            "actions": [{"type": "notify", "value": "requester"}],
        },
        headers=headers,
    )
    await _ticket(client, key, ["vip"])

    db_session.expire_all()
    notified = [
        e
        for e in (await db_session.execute(select(NotifyrEvent))).scalars().all()
        if e.event == "ticket.notified"
    ]
    assert len(notified) == 1
    assert notified[0].recipient == "dara@example.com"
    assert notified[0].payload["variables"]["source"] == "trigger:Tell the requester"


async def test_automation_notify_action(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "notifyr_api_url", "https://notifyr.test")
    monkeypatch.setattr(settings, "notifyr_api_key", "nkey")
    headers, key = await _workspace(client, email="notify-auto@example.com")
    await client.post(
        "/api/v1/automations",
        json={
            "name": "Nudge agents",
            "after_minutes": 0,
            "conditions": [{"field": "status", "op": "is", "value": "open"}],
            "actions": [{"type": "notify", "value": "agents"}],
        },
        headers=headers,
    )
    await _ticket(client, key)

    from app.services import automations as svc

    assert await svc.sweep_automations(db_session) == 1
    db_session.expire_all()
    notified = [
        e
        for e in (await db_session.execute(select(NotifyrEvent))).scalars().all()
        if e.event == "ticket.notified"
    ]
    assert len(notified) == 1
    assert notified[0].recipient is None
