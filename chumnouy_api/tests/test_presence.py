"""Ticket presence: heartbeat and viewers (stale rows age out)."""
from datetime import timedelta
from uuid import UUID

import pytest

from app.models import TicketPresence, User, utcnow

pytestmark = pytest.mark.asyncio


async def _owner(client, *, email):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": "Acme"},
    )
    assert signup.status_code == 201, signup.text
    data = signup.json()
    headers = {"Authorization": f"Bearer {data['token']}"}
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
    return data["user"]["id"], headers, key


async def test_heartbeat_and_viewers(client):
    user_id, headers, key = await _owner(client, email="presence@example.com")
    ticket_id = (
        await client.post(
            "/api/v1/tickets",
            json={"subject": "Hi", "message": "hello", "requester": {"external_id": "c1"}},
            headers={"X-Api-Key": key},
        )
    ).json()["id"]

    beat = await client.post(f"/api/v1/tickets/{ticket_id}/presence", headers=headers)
    assert beat.status_code == 200, beat.text
    assert user_id in beat.json()["viewers"]

    read = await client.get(f"/api/v1/tickets/{ticket_id}/presence", headers=headers)
    assert user_id in read.json()["viewers"]


async def test_stale_viewers_age_out(client, db_session):
    _, headers, key = await _owner(client, email="presence2@example.com")
    ticket_id = (
        await client.post(
            "/api/v1/tickets",
            json={"subject": "Hi", "message": "hello", "requester": {"external_id": "c1"}},
            headers={"X-Api-Key": key},
        )
    ).json()["id"]

    other = User(email="other@example.com", password_hash="x", name="Other")
    db_session.add(other)
    await db_session.flush()
    db_session.add(
        TicketPresence(
            ticket_id=UUID(ticket_id),
            user_id=other.id,
            last_seen_at=utcnow() - timedelta(minutes=10),
        )
    )
    await db_session.commit()

    read = await client.get(f"/api/v1/tickets/{ticket_id}/presence", headers=headers)
    assert str(other.id) not in [str(v) for v in read.json()["viewers"]]


async def test_presence_requires_auth(client):
    assert (await client.get("/api/v1/tickets/11111111-1111-1111-1111-111111111111/presence")).status_code == 401
