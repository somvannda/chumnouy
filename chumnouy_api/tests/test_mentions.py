"""@mentions on internal notes notify the mentioned workspace members."""
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
    data = signup.json()
    headers = {"Authorization": f"Bearer {data['token']}"}
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
    return data["user"]["id"], headers, key


async def _events(db_session):
    db_session.expire_all()
    return (await db_session.execute(select(NotifyrEvent))).scalars().all()


async def test_internal_mention_notifies_the_member(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "notifyr_api_url", "https://notifyr.test")
    monkeypatch.setattr(settings, "notifyr_api_key", "nkey")
    user_id, headers, key = await _workspace(client, email="mention@example.com")
    ticket_id = (
        await client.post(
            "/api/v1/tickets",
            json={"subject": "Hi", "message": "hello", "requester": {"external_id": "c1"}},
            headers={"X-Api-Key": key},
        )
    ).json()["id"]

    resp = await client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        json={"body": "Internal: please look", "visibility": "internal", "mentions": [user_id]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    mentions = [e for e in await _events(db_session) if e.event == "ticket.mentioned"]
    assert len(mentions) == 1
    assert mentions[0].recipient == "mention@example.com"


async def test_public_reply_does_not_notify_mentions(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "notifyr_api_url", "https://notifyr.test")
    monkeypatch.setattr(settings, "notifyr_api_key", "nkey")
    user_id, headers, key = await _workspace(client, email="mention2@example.com")
    ticket_id = (
        await client.post(
            "/api/v1/tickets",
            json={"subject": "Hi", "message": "hello", "requester": {"external_id": "c1"}},
            headers={"X-Api-Key": key},
        )
    ).json()["id"]

    await client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        json={"body": "public", "visibility": "public", "mentions": [user_id]},
        headers=headers,
    )
    assert [e for e in await _events(db_session) if e.event == "ticket.mentioned"] == []
