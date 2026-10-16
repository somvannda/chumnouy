"""Live chat: requester session + agent reply/close, SSE stream, Notifyr nudge."""
import pytest
from sqlalchemy import select

from app.models import NotifyrEvent

pytestmark = pytest.mark.asyncio

EARLY = "2000-01-01T00:00:00Z"


async def _workspace(client, *, email, requester_external_id="c1", requester_email=None):
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
    requester_payload = {"external_id": requester_external_id}
    if requester_email:
        requester_payload["email"] = requester_email
    await client.post(
        "/api/v1/tickets",
        json={"subject": "Hi", "message": "hello", "requester": requester_payload},
        headers={"X-Api-Key": key},
    )
    requester = (
        await client.get(f"/api/v1/requesters?q={requester_external_id}", headers=headers)
    ).json()[0]
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
    assert (
        await client.get(
            f"/api/v1/public/chat/sessions/{session_id}/stream?timeout=1", headers=portal_b
        )
    ).status_code == 404


async def test_chat_stream_replays_messages(client):
    headers, portal = await _workspace(client, email="chatstream@example.com")
    session_id = (await client.post("/api/v1/public/chat/sessions", headers=portal)).json()["id"]
    await client.post(
        f"/api/v1/public/chat/sessions/{session_id}/messages",
        json={"body": "Hello there"},
        headers=portal,
    )
    await client.post(
        f"/api/v1/console/chat/sessions/{session_id}/messages",
        json={"body": "Agent here"},
        headers=headers,
    )

    requester_stream = await client.get(
        f"/api/v1/public/chat/sessions/{session_id}/stream?after={EARLY}&timeout=1", headers=portal
    )
    assert requester_stream.status_code == 200, requester_stream.text
    assert requester_stream.headers["content-type"].startswith("text/event-stream")
    assert "event: ready" in requester_stream.text
    assert "Hello there" in requester_stream.text
    assert "Agent here" in requester_stream.text
    assert "event: done" in requester_stream.text

    agent_stream = await client.get(
        f"/api/v1/console/chat/sessions/{session_id}/stream?after={EARLY}&timeout=1", headers=headers
    )
    assert agent_stream.status_code == 200, agent_stream.text
    assert "Agent here" in agent_stream.text


async def test_agent_reply_nudges_requester_via_notifyr(client, db_session):
    headers, portal = await _workspace(
        client,
        email="chatnudge@example.com",
        requester_external_id="n1",
        requester_email="n1@example.com",
    )
    session_id = (await client.post("/api/v1/public/chat/sessions", headers=portal)).json()["id"]

    await client.post(
        f"/api/v1/public/chat/sessions/{session_id}/messages",
        json={"body": "anyone?"},
        headers=portal,
    )
    assert (await db_session.execute(select(NotifyrEvent))).scalars().all() == []

    await client.patch(
        "/api/v1/console/settings/notifications",
        json={"notifyr_api_url": "https://notifyr.test", "notifyr_api_key": "secret"},
        headers=headers,
    )
    await client.post(
        f"/api/v1/console/chat/sessions/{session_id}/messages",
        json={"body": "On it"},
        headers=headers,
    )

    events = (await db_session.execute(select(NotifyrEvent))).scalars().all()
    assert len(events) == 1
    event = events[0]
    assert event.event == "chat.replied"
    assert event.ticket_id is None
    assert event.recipient == "n1@example.com"
    assert event.payload["chat"]["session_id"] == session_id
    assert event.payload["variables"]["message"] == "On it"
    assert event.status == "pending"


async def test_requester_messages_do_not_nudge(client, db_session):
    headers, portal = await _workspace(
        client,
        email="chatquiet@example.com",
        requester_external_id="q1",
        requester_email="q1@example.com",
    )
    await client.patch(
        "/api/v1/console/settings/notifications",
        json={"notifyr_api_url": "https://notifyr.test", "notifyr_api_key": "secret"},
        headers=headers,
    )
    session_id = (await client.post("/api/v1/public/chat/sessions", headers=portal)).json()["id"]
    await client.post(
        f"/api/v1/public/chat/sessions/{session_id}/messages",
        json={"body": "hello"},
        headers=portal,
    )
    assert (await db_session.execute(select(NotifyrEvent))).scalars().all() == []
