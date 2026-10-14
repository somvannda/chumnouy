import pytest

pytestmark = pytest.mark.asyncio


async def test_signup_creates_workspace_and_token(client, signup_payload):
    resp = await client.post("/api/v1/auth/signup", json=signup_payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["token"]
    assert body["user"]["email"] == "owner@example.com"
    assert body["workspace"]["role"] == "owner"
    assert body["workspace"]["slug"] == "acme-support"


async def test_signup_rejects_duplicate_email(client, signup_payload):
    first = await client.post("/api/v1/auth/signup", json=signup_payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/auth/signup", json=signup_payload)
    assert second.status_code == 409


async def test_signup_rejects_short_password(client, signup_payload):
    resp = await client.post("/api/v1/auth/signup", json={**signup_payload, "password": "short"})
    assert resp.status_code == 422


async def test_login_and_me(client, signup_payload):
    await client.post("/api/v1/auth/signup", json=signup_payload)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": signup_payload["email"], "password": signup_payload["password"]},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["token"]

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "owner@example.com"
    assert len(me.json()["workspaces"]) == 1
    assert me.json()["workspaces"][0]["role"] == "owner"


async def test_login_rejects_wrong_password(client, signup_payload):
    await client.post("/api/v1/auth/signup", json=signup_payload)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": signup_payload["email"], "password": "not-the-password"},
    )
    assert resp.status_code == 401


async def test_me_requires_auth(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
