"""Live chat: requester session + agent reply/close."""
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
        json={"subject": "Hi", "message": "hello", "requester": {"external_id": "c1"}},
        headers={"X-Api-Key": key},
    )
    requester = (await client.get("/api/v1/requesters?q=c1", headers=headers)).json()[0]
    token = (
        await client.post(f"/api/v1/requesters/{requester['id']}/portal-token", headers=headers)
    ).json()["token"]
    return headers, {"X-Requester-Token": token}


async def test_chat_session_roundtrip(client):
    headers, portal = await _workspace(client, email="chat@example.com")

    created = await client.post("/api/v1/public/chat/sessions", headers=portal)
    assert created.status_code == 201, created.text
    session_id = created.json()["id"]

    sent = await client.post(
        f"/api/v1/public/chat/sessions/{session_id}/messages",
        json={"body": "Hello, is anyone there?"},
        headers=portal,
    )
    assert sent.status_code == 201, sent.text
    assert sent.json()["author_type"] == "requester"

    listing = await client.get("/api/v1/console/chat/sessions?status=open", headers=headers)
    assert [s["id"] for s in listing.json()] == [session_id]

    reply = await client.post(
        f"/api/v1/console/chat/sessions/{session_id}/messages",
        json={"body": "Hi! How can I help?"},
        headers=headers,
    )
    assert reply.json()["author_type"] == "agent"

    detail = await client.get(f"/api/v1/public/chat/sessions/{session_id}", headers=portal)
    assert [m["author_type"] for m in detail.json()["messages"]] == ["requester", "agent"]

    closed = await client.post(f"/api/v1/console/chat/sessions/{session_id}/close", headers=headers)
    assert closed.json()["status"] == "closed"

    after_close = await client.post(
        f"/api/v1/public/chat/sessions/{session_id}/messages",
        json={"body": "one more"},
        headers=portal,
    )
    assert after_close.status_code == 409


async def test_chat_sessions_are_scoped(client):
    _, portal_a = await _workspace(client, email="chata@example.com")
    _, portal_b = await _workspace(client, email="chatb@example.com")
    session_id = (await client.post("/api/v1/public/chat/sessions", headers=portal_a)).json()["id"]

    assert (await client.get(f"/api/v1/public/chat/sessions/{session_id}", headers=portal_b)).status_code == 404
