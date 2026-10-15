"""Teams CRUD, membership, ticket assignment and role gating."""
import pytest
from sqlalchemy import select

from app.models import Membership

pytestmark = pytest.mark.asyncio


async def _owner(client, *, email, workspace="Acme Support"):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
    )
    assert signup.status_code == 201, signup.text
    data = signup.json()
    return data["user"]["id"], {"Authorization": f"Bearer {data['token']}"}


async def _key(client, headers, *, scopes=("tickets:read", "tickets:write")):
    integration = await client.post(
        "/api/v1/integrations", json={"name": "POS", "scopes": list(scopes)}, headers=headers
    )
    return (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]


async def _set_role(db_session, email, role):
    from app.models import User

    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    membership = (
        await db_session.execute(select(Membership).where(Membership.user_id == user.id))
    ).scalar_one()
    membership.role = role
    await db_session.commit()


async def test_team_crud_and_membership(client):
    user_id, headers = await _owner(client, email="teams@example.com")

    created = await client.post(
        "/api/v1/teams", json={"name": "Hardware Support"}, headers=headers
    )
    assert created.status_code == 201, created.text
    team = created.json()
    assert team["slug"] == "hardware-support"
    team_id = team["id"]

    added = await client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"user_id": user_id, "role": "lead"},
        headers=headers,
    )
    assert added.status_code == 201, added.text
    assert added.json()["members"] == [{"user_id": user_id, "role": "lead"}]

    listed = await client.get("/api/v1/teams", headers=headers)
    assert [t["id"] for t in listed.json()] == [team_id]

    renamed = await client.patch(
        f"/api/v1/teams/{team_id}", json={"name": "Hardware"}, headers=headers
    )
    assert renamed.json()["slug"] == "hardware"

    removed = await client.delete(f"/api/v1/teams/{team_id}/members/{user_id}", headers=headers)
    assert removed.json()["members"] == []

    deleted = await client.delete(f"/api/v1/teams/{team_id}", headers=headers)
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/teams", headers=headers)).json() == []


async def test_ticket_can_be_assigned_to_a_team(client):
    _, headers = await _owner(client, email="assign@example.com")
    key = await _key(client, headers)
    team_id = (
        await client.post("/api/v1/teams", json={"name": "Billing"}, headers=headers)
    ).json()["id"]

    ticket = await client.post(
        "/api/v1/tickets",
        json={"subject": "Invoice", "message": "hi", "requester": {"external_id": "c1"}},
        headers={"X-Api-Key": key},
    )
    ticket_id = ticket.json()["id"]
    assert ticket.json()["team_id"] is None

    updated = await client.patch(
        f"/api/v1/tickets/{ticket_id}", json={"team_id": team_id}, headers=headers
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["team_id"] == team_id


async def test_teams_require_the_manage_permission(client, db_session):
    _, headers = await _owner(client, email="viewer@example.com")
    await _set_role(db_session, "viewer@example.com", "viewer")

    denied = await client.post("/api/v1/teams", json={"name": "Nope"}, headers=headers)
    assert denied.status_code == 403
    assert (await client.get("/api/v1/teams", headers=headers)).status_code == 403


async def test_teams_are_workspace_isolated(client):
    _, headers_a = await _owner(client, email="a@example.com", workspace="Workspace A")
    _, headers_b = await _owner(client, email="b@example.com", workspace="Workspace B")
    team_id = (
        await client.post("/api/v1/teams", json={"name": "Only A"}, headers=headers_a)
    ).json()["id"]

    assert (await client.get("/api/v1/teams", headers=headers_b)).json() == []
    assert (await client.get(f"/api/v1/teams/{team_id}", headers=headers_b)).status_code == 404
