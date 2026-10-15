"""SSO (OIDC): settings, authorize URL, callback and domain checks."""
import pytest

from app.services import sso as sso_svc

pytestmark = pytest.mark.asyncio


async def _owner(client, *, email, workspace="Acme Support"):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
    )
    assert signup.status_code == 201, signup.text
    data = signup.json()
    return data["workspace"]["slug"], {"Authorization": f"Bearer {data['token']}"}


async def _enable_sso(client, headers, *, domains=None):
    resp = await client.patch(
        "/api/v1/console/settings/sso",
        json={
            "enabled": True,
            "issuer": "https://idp.example.com",
            "client_id": "chumnouy",
            "client_secret": "secret",
            "allowed_domains": domains or [],
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_sso_settings_and_start(client):
    slug, headers = await _owner(client, email="sso@example.com")
    settings = await _enable_sso(client, headers)
    assert settings["sso"]["enabled"] is True
    assert settings["sso"]["client_id"] == "chumnouy"
    assert settings["sso"]["client_secret_set"] is True
    assert "client_secret" not in settings["sso"]

    start = await client.get(f"/api/v1/auth/sso/{slug}")
    assert start.status_code == 200, start.text
    assert start.json()["authorize_url"].startswith("https://idp.example.com/authorize?")
    assert "client_id=chumnouy" in start.json()["authorize_url"]
    assert start.json()["state"]


async def test_sso_callback_provisions_a_user(client, monkeypatch):
    slug, headers = await _owner(client, email="sso2@example.com")
    await _enable_sso(client, headers, domains=["example.com"])
    state = (await client.get(f"/api/v1/auth/sso/{slug}")).json()["state"]

    async def fake_exchange(config, code):
        return {"id_token": "fake-token"}

    def fake_claims(id_token, config):
        return {"email": "newbie@example.com", "name": "New Bie"}

    monkeypatch.setattr(sso_svc, "_exchange_code", fake_exchange)
    monkeypatch.setattr(sso_svc, "_claims", fake_claims)

    resp = await client.get(f"/api/v1/auth/sso/callback?code=abc&state={state}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token"]
    assert body["user"]["email"] == "newbie@example.com"
    assert body["workspace"]["slug"] == slug


async def test_sso_rejects_a_disallowed_domain(client, monkeypatch):
    slug, headers = await _owner(client, email="sso3@example.com")
    await _enable_sso(client, headers, domains=["allowed.com"])
    state = (await client.get(f"/api/v1/auth/sso/{slug}")).json()["state"]

    async def fake_exchange(config, code):
        return {"id_token": "fake-token"}

    def fake_claims(id_token, config):
        return {"email": "someone@elsewhere.com"}

    monkeypatch.setattr(sso_svc, "_exchange_code", fake_exchange)
    monkeypatch.setattr(sso_svc, "_claims", fake_claims)

    resp = await client.get(f"/api/v1/auth/sso/callback?code=abc&state={state}")
    assert resp.status_code == 400
    assert "domain" in resp.json()["error"]["message"].lower()


async def test_sso_start_404_when_not_enabled(client):
    slug, _ = await _owner(client, email="sso4@example.com")
    assert (await client.get(f"/api/v1/auth/sso/{slug}")).status_code == 404
    assert (await client.get("/api/v1/auth/sso/nope")).status_code == 404
