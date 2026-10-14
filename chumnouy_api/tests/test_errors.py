"""Uniform error envelope: {"error": {"code", "message", "details"}}."""
import pytest

pytestmark = pytest.mark.asyncio


async def _signup(client, email="envelope@example.com"):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": "Acme"},
    )
    assert signup.status_code == 201, signup.text
    return {"Authorization": f"Bearer {signup.json()['token']}"}


async def test_unauthorized_envelope(client):
    resp = await client.get("/api/v1/tickets")
    assert resp.status_code == 401
    body = resp.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "unauthorized"
    assert body["error"]["message"]
    assert body["error"]["details"] == {}


async def test_validation_envelope(client):
    resp = await client.post("/api/v1/auth/signup", json={"email": "not-an-email"})
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["errors"]


async def test_not_found_envelope(client):
    headers = await _signup(client)
    resp = await client.get(
        "/api/v1/tickets/11111111-1111-1111-1111-111111111111", headers=headers
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Ticket not found"
    assert "detail" not in body
