"""Widget branding: console-managed, public-readable (P6)."""
import pytest

pytestmark = pytest.mark.asyncio


async def _portal(client, *, email):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": "Acme"},
    )
    assert signup.status_code == 201, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}
    integration = await client.post(
        "/api/v1/integrations",
        json={"name": "POS", "scopes": ["tickets:read", "tickets:write", "requesters:write"]},
        headers=headers,
    )
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]
    await client.post(
        "/api/v1/tickets",
        json={"subject": "Hi", "message": "hello", "requester": {"external_id": "b1"}},
        headers={"X-Api-Key": key},
    )
    requester = (await client.get("/api/v1/requesters?q=b1", headers=headers)).json()[0]
    token = (
        await client.post(f"/api/v1/requesters/{requester['id']}/portal-token", headers=headers)
    ).json()["token"]
    return headers, {"X-Requester-Token": token}


async def test_branding_defaults_then_updated(client):
    headers, portal = await _portal(client, email="brand@example.com")

    defaults = await client.get("/api/v1/public/branding", headers=portal)
    assert defaults.status_code == 200, defaults.text
    assert defaults.json() == {
        "title": "Support",
        "label": "Support",
        "accent": "#6957f5",
        "position": "right",
        "greeting": None,
        "pre_chat": False,
    }

    updated = await client.patch(
        "/api/v1/console/settings/branding",
        json={
            "title": "Acme Help",
            "label": "Chat",
            "accent": "#0ea5e9",
            "position": "left",
            "greeting": "Hi! Ask us anything.",
            "pre_chat": True,
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["branding"]["title"] == "Acme Help"

    public = await client.get("/api/v1/public/branding", headers=portal)
    assert public.json()["label"] == "Chat"
    assert public.json()["accent"] == "#0ea5e9"
    assert public.json()["position"] == "left"
    assert public.json()["pre_chat"] is True


async def test_branding_rejects_bad_accent(client):
    headers, portal = await _portal(client, email="brand2@example.com")
    await client.patch(
        "/api/v1/console/settings/branding",
        json={"accent": "not-a-colour"},
        headers=headers,
    )
    assert (await client.get("/api/v1/public/branding", headers=portal)).json()["accent"] == "#6957f5"


async def test_branding_is_per_workspace(client):
    headers_a, portal_a = await _portal(client, email="branda@example.com")
    _, portal_b = await _portal(client, email="brandb@example.com")
    await client.patch(
        "/api/v1/console/settings/branding", json={"title": "A only"}, headers=headers_a
    )
    assert (await client.get("/api/v1/public/branding", headers=portal_b)).json()["title"] == "Support"
