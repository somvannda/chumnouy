"""Account/workspace-level audit events (settings and member changes)."""
import pytest

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


async def test_settings_changes_are_audited(client):
    headers, _ = await _workspace(client, email="auditsettings@example.com")

    await client.patch(
        "/api/v1/console/settings/branding",
        json={"title": "Acme Help", "accent": "#0ea5e9"},
        headers=headers,
    )
    await client.patch("/api/v1/console/settings/locale", json={"locale": "km"}, headers=headers)

    events = (await client.get("/api/v1/audit/workspace", headers=headers)).json()["data"]
    types = [event["type"] for event in events]
    assert types[0] == "settings.locale"  # newest first
    assert "settings.branding" in types

    branding = next(event for event in events if event["type"] == "settings.branding")
    assert branding["data"]["title"] == "Acme Help"
    assert branding["data"]["accent"] == "#0ea5e9"
    assert branding["actor_type"] == "user"

    filtered = (
        await client.get("/api/v1/audit/workspace?type=settings.locale", headers=headers)
    ).json()["data"]
    assert [event["type"] for event in filtered] == ["settings.locale"]
    assert filtered[0]["data"] == {"locale": "km"}


async def test_secrets_never_reach_the_audit_trail(client):
    headers, _ = await _workspace(client, email="auditsecrets@example.com")

    await client.patch(
        "/api/v1/console/settings/sso",
        json={
            "enabled": True,
            "issuer": "https://idp.example.com",
            "client_id": "abc",
            "client_secret": "super-secret-value",
        },
        headers=headers,
    )
    await client.patch(
        "/api/v1/console/settings/notifications",
        json={"notifyr_api_url": "https://notifyr.test", "notifyr_api_key": "nkey_secret"},
        headers=headers,
    )

    events = (await client.get("/api/v1/audit/workspace", headers=headers)).json()["data"]
    sso = next(event for event in events if event["type"] == "settings.sso")
    notifications = next(event for event in events if event["type"] == "settings.notifications")
    assert "client_secret" not in sso["data"]
    assert sso["data"]["issuer"] == "https://idp.example.com"
    assert "notifyr_api_key" not in notifications["data"]
    assert "super-secret-value" not in str(events)
    assert "nkey_secret" not in str(events)


async def test_member_changes_are_audited(client):
    headers, _ = await _workspace(client, email="auditmembers@example.com")

    invited = await client.post(
        "/api/v1/members/invites",
        json={"email": "newbie@example.com", "role": "agent"},
        headers=headers,
    )
    assert invited.status_code == 201, invited.text
    accepted = await client.post(
        "/api/v1/auth/invite/accept",
        json={"token": invited.json()["token"], "password": "supersecret123"},
    )
    user_id = accepted.json()["user"]["id"]

    await client.patch(
        f"/api/v1/members/{user_id}", json={"role": "admin", "skills": ["billing"]}, headers=headers
    )
    await client.delete(f"/api/v1/members/{user_id}", headers=headers)

    events = (await client.get("/api/v1/audit/workspace", headers=headers)).json()["data"]
    types = [event["type"] for event in events]
    assert types[:3] == ["member.removed", "member.updated", "member.invited"]

    updated = events[1]
    assert updated["data"]["role"] == "admin"
    assert updated["data"]["skills"] == ["billing"]
    assert events[2]["data"]["email"] == "newbie@example.com"


async def test_workspace_events_are_separate_and_scoped(client):
    headers_a, key_a = await _workspace(client, email="auditscopea@example.com")
    headers_b, _ = await _workspace(client, email="auditscopeb@example.com")

    # A ticket write is a ticket event, not a workspace event.
    await client.post(
        "/api/v1/tickets",
        json={"subject": "Hi", "message": "hello", "requester": {"external_id": "c1"}},
        headers={"X-Api-Key": key_a},
    )
    await client.patch(
        "/api/v1/console/settings/locale", json={"locale": "km"}, headers=headers_a
    )

    assert (await client.get("/api/v1/audit?type=ticket.created", headers=headers_a)).json()["data"]
    workspace_events = (await client.get("/api/v1/audit/workspace", headers=headers_a)).json()
    assert [event["type"] for event in workspace_events["data"]] == ["settings.locale"]

    # Workspace B sees none of it.
    assert (await client.get("/api/v1/audit/workspace", headers=headers_b)).json()["data"] == []

    # An integration key with the read scope can read the trail too.
    key_events = await client.get(
        "/api/v1/audit/workspace", headers={"X-Api-Key": key_a}
    )
    assert key_events.status_code == 200, key_events.text
