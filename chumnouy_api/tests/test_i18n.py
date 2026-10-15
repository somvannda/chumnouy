"""Workspace locale: console setting, surfaced to Notifyr for localised delivery."""
import pytest
from sqlalchemy import select

from app.config import settings
from app.models import NotifyrEvent

pytestmark = pytest.mark.asyncio


async def _owner(client, *, email):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": "Acme"},
    )
    assert signup.status_code == 201, signup.text
    return {"Authorization": f"Bearer {signup.json()['token']}"}


async def test_locale_defaults_to_en_and_can_be_set(client):
    headers = await _owner(client, email="locale@example.com")
    read = await client.get("/api/v1/console/settings", headers=headers)
    assert read.json()["locale"] == "en"

    updated = await client.patch(
        "/api/v1/console/settings/locale", json={"locale": "km"}, headers=headers
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["locale"] == "km"
    assert (await client.get("/api/v1/console/settings", headers=headers)).json()["locale"] == "km"


async def test_notifyr_event_carries_the_locale(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "notifyr_api_url", "https://notifyr.test")
    monkeypatch.setattr(settings, "notifyr_api_key", "nkey")
    headers = await _owner(client, email="locale2@example.com")
    await client.patch("/api/v1/console/settings/locale", json={"locale": "km"}, headers=headers)

    integration = await client.post(
        "/api/v1/integrations",
        json={"name": "POS", "scopes": ["tickets:write"]},
        headers=headers,
    )
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]
    await client.post(
        "/api/v1/tickets",
        json={"subject": "Hi", "message": "hello", "requester": {"external_id": "c1"}},
        headers={"X-Api-Key": key},
    )

    db_session.expire_all()
    events = (await db_session.execute(select(NotifyrEvent))).scalars().all()
    assert len(events) == 1
    assert events[0].payload["variables"]["locale"] == "km"
