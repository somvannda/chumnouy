"""Routing: round-robin, load-balanced and forced assignment."""
import pytest
from sqlalchemy import select

from app.models import Membership, User, Workspace

pytestmark = pytest.mark.asyncio


async def _workspace(client, *, email, scopes=("tickets:read", "tickets:write")):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": "Acme"},
    )
    assert signup.status_code == 201, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}
    integration = await client.post(
        "/api/v1/integrations",
        json={"name": "POS", "scopes": list(scopes)},
        headers=headers,
    )
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]
    return headers, key


async def _add_agent(db_session, workspace_id, email):
    user = User(email=email, password_hash="x", name=email.split("@")[0])
    db_session.add(user)
    await db_session.flush()
    db_session.add(Membership(workspace_id=workspace_id, user_id=user.id, role="agent"))
    await db_session.commit()
    return str(user.id)


async def _ticket(client, key, external_id="c1"):
    resp = await client.post(
        "/api/v1/tickets",
        json={"subject": "Hi", "message": "hello", "requester": {"external_id": external_id}},
        headers={"X-Api-Key": key},
    )
    return resp.json()["id"]


async def test_round_robin_then_load_balanced(client, db_session):
    headers, key = await _workspace(client, email="routing@example.com")
    workspace = (await db_session.execute(select(Workspace))).scalars().first()
    await _add_agent(db_session, workspace.id, "a-agent@example.com")
    await _add_agent(db_session, workspace.id, "b-agent@example.com")

    first = await _ticket(client, key, "c1")
    second = await _ticket(client, key, "c2")

    round_robin = await client.post(
        f"/api/v1/tickets/{first}/assign", json={"strategy": "round_robin"}, headers=headers
    )
    assert round_robin.status_code == 200, round_robin.text
    assignee = round_robin.json()["assignee_user_id"]
    assert assignee is not None

    load_balanced = await client.post(
        f"/api/v1/tickets/{second}/assign", json={"strategy": "load_balanced"}, headers=headers
    )
    # The first assignee now has one open ticket, so the balanced pick differs.
    assert load_balanced.json()["assignee_user_id"] != assignee

    audit = await client.get("/api/v1/audit?type=ticket.assigned", headers=headers)
    assert audit.json()["data"]


async def test_forced_user_and_team_assignment(client, db_session):
    headers, key = await _workspace(client, email="routing2@example.com")
    workspace = (await db_session.execute(select(Workspace))).scalars().first()
    agent = await _add_agent(db_session, workspace.id, "solo-agent@example.com")
    team_id = (
        await client.post("/api/v1/teams", json={"name": "Tier 1"}, headers=headers)
    ).json()["id"]
    ticket_id = await _ticket(client, key)

    forced = await client.post(
        f"/api/v1/tickets/{ticket_id}/assign",
        json={"user_id": agent, "team_id": team_id},
        headers=headers,
    )
    assert forced.status_code == 200, forced.text
    assert forced.json()["assignee_user_id"] == agent
    assert forced.json()["team_id"] == team_id


async def test_assign_requires_write_scope(client):
    _, key = await _workspace(client, email="routing3@example.com", scopes=("tickets:read",))
    denied = await client.post(
        "/api/v1/tickets/11111111-1111-1111-1111-111111111111/assign",
        json={"strategy": "round_robin"},
        headers={"X-Api-Key": key},
    )
    assert denied.status_code == 403
