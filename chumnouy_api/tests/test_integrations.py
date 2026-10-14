import pytest

pytestmark = pytest.mark.asyncio


async def _signup(client, payload) -> str:
    resp = await client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


async def test_create_integration_and_use_key(client, signup_payload):
    token = await _signup(client, signup_payload)
    headers = {"Authorization": f"Bearer {token}"}

    integration = await client.post(
        "/api/v1/integrations",
        json={"name": "Chmaba POS", "scopes": ["tickets:read", "tickets:write"]},
        headers=headers,
    )
    assert integration.status_code == 201, integration.text
    assert integration.json()["slug"] == "chmaba-pos"
    integration_id = integration.json()["id"]

    key_resp = await client.post(
        f"/api/v1/integrations/{integration_id}/keys",
        json={"name": "production", "environment": "live"},
        headers=headers,
    )
    assert key_resp.status_code == 201, key_resp.text
    raw = key_resp.json()["key"]
    assert raw.startswith("chm_live_")
    assert key_resp.json()["api_key"]["key_prefix"] == raw[:16]

    who = await client.get("/api/v1/whoami", headers={"X-Api-Key": raw})
    assert who.status_code == 200, who.text
    assert who.json()["workspace"] == "acme-support"
    assert who.json()["integration"] == "chmaba-pos"
    assert set(who.json()["scopes"]) == {"tickets:read", "tickets:write"}


async def test_whoami_rejects_unknown_key(client):
    resp = await client.get("/api/v1/whoami", headers={"X-Api-Key": "chm_live_not-a-real-key"})
    assert resp.status_code == 401


async def test_revoked_key_is_rejected(client, signup_payload):
    token = await _signup(client, signup_payload)
    headers = {"Authorization": f"Bearer {token}"}
    integration = await client.post("/api/v1/integrations", json={"name": "POS"}, headers=headers)
    integration_id = integration.json()["id"]
    key_resp = await client.post(
        f"/api/v1/integrations/{integration_id}/keys", json={"name": "k"}, headers=headers
    )
    raw = key_resp.json()["key"]
    key_id = key_resp.json()["api_key"]["id"]

    revoke = await client.post(f"/api/v1/integrations/keys/{key_id}/revoke", headers=headers)
    assert revoke.status_code == 200
    assert revoke.json()["is_active"] is False

    who = await client.get("/api/v1/whoami", headers={"X-Api-Key": raw})
    assert who.status_code == 401


async def test_key_scopes_are_restricted(client, signup_payload):
    token = await _signup(client, signup_payload)
    headers = {"Authorization": f"Bearer {token}"}
    integration = await client.post("/api/v1/integrations", json={"name": "POS"}, headers=headers)
    integration_id = integration.json()["id"]
    # An unknown scope is dropped; no scope given falls back to the safe default.
    key_resp = await client.post(
        f"/api/v1/integrations/{integration_id}/keys",
        json={"name": "k", "scopes": ["not:a:scope"]},
        headers=headers,
    )
    assert key_resp.json()["api_key"]["scopes"] == ["tickets:read"]


async def test_integrations_require_auth(client):
    resp = await client.get("/api/v1/integrations")
    assert resp.status_code == 401
