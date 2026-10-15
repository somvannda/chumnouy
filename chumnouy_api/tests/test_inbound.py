"""Inbound email → ticket: create, threading and scope."""
import pytest

pytestmark = pytest.mark.asyncio


async def _workspace(client, *, email, scopes=("tickets:read", "tickets:write")):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": "Acme"},
    )
    assert signup.status_code == 201, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}
    integration = await client.post(
        "/api/v1/integrations", json={"name": "Notifyr", "scopes": list(scopes)}, headers=headers
    )
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]
    return headers, key


def _email(**overrides):
    payload = {
        "from_email": "dara@example.com",
        "from_name": "Sok Dara",
        "subject": "Card reader down",
        "body": "The terminal stopped charging.",
        "message_id": "<msg-1@mail>",
    }
    payload.update(overrides)
    return payload


async def test_new_email_creates_a_ticket_and_requester(client):
    _, key = await _workspace(client, email="inbound@example.com")
    resp = await client.post("/api/v1/inbound/email", json=_email(), headers={"X-Api-Key": key})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["reference"].startswith("CMY-")
    assert body["requester"]["email"] == "dara@example.com"
    assert body["messages"][0]["body"] == "The terminal stopped charging."


async def test_reply_threads_by_in_reply_to(client):
    headers, key = await _workspace(client, email="inbound2@example.com")
    created = await client.post("/api/v1/inbound/email", json=_email(), headers={"X-Api-Key": key})
    ticket_id = created.json()["id"]

    reply = await client.post(
        "/api/v1/inbound/email",
        json=_email(
            subject="Re: Card reader down",
            body="Any update?",
            message_id="<msg-2@mail>",
            in_reply_to="<msg-1@mail>",
        ),
        headers={"X-Api-Key": key},
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["id"] == ticket_id
    assert len(reply.json()["messages"]) == 2
    assert reply.json()["messages"][-1]["body"] == "Any update?"

    # A reply without in_reply_to still lands on the sender's open ticket.
    follow_up = await client.post(
        "/api/v1/inbound/email",
        json=_email(subject="Re: again", body="Third message", message_id="<msg-3@mail>"),
        headers={"X-Api-Key": key},
    )
    assert follow_up.json()["id"] == ticket_id
    assert len(follow_up.json()["messages"]) == 3


async def test_inbound_requires_write_scope(client):
    _, key = await _workspace(client, email="inbound3@example.com", scopes=("tickets:read",))
    resp = await client.post("/api/v1/inbound/email", json=_email(), headers={"X-Api-Key": key})
    assert resp.status_code == 403
