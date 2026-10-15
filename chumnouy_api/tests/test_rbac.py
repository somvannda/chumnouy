"""Granular RBAC: roles gate management and ticket writes for console users."""
import pytest
from sqlalchemy import select

from app.models import Membership, User

pytestmark = pytest.mark.asyncio


async def _owner(client, *, email, workspace="Acme Support"):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
    )
    assert signup.status_code == 201, signup.text
    return {"Authorization": f"Bearer {signup.json()['token']}"}


async def _set_role(db_session, email, role):
    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    membership = (
        await db_session.execute(select(Membership).where(Membership.user_id == user.id))
    ).scalar_one()
    membership.role = role
    await db_session.commit()


def _ticket():
    return {"subject": "Hi", "message": "hello", "requester": {"external_id": "c1"}}


async def test_viewer_is_read_only(client, db_session):
    headers = await _owner(client, email="rbac-viewer@example.com")
    await _set_role(db_session, "rbac-viewer@example.com", "viewer")

    assert (await client.get("/api/v1/tickets", headers=headers)).status_code == 200
    assert (await client.post("/api/v1/tickets", json=_ticket(), headers=headers)).status_code == 403
    assert (await client.get("/api/v1/console/settings", headers=headers)).status_code == 403
    assert (await client.get("/api/v1/integrations", headers=headers)).status_code == 403
    assert (await client.get("/api/v1/teams", headers=headers)).status_code == 403


async def test_agent_writes_tickets_but_cannot_manage(client, db_session):
    headers = await _owner(client, email="rbac-agent@example.com")
    await _set_role(db_session, "rbac-agent@example.com", "agent")

    assert (await client.post("/api/v1/tickets", json=_ticket(), headers=headers)).status_code == 201
    assert (await client.get("/api/v1/console/settings", headers=headers)).status_code == 403
    assert (await client.get("/api/v1/integrations", headers=headers)).status_code == 403


async def test_team_lead_manages_teams_not_settings(client, db_session):
    headers = await _owner(client, email="rbac-lead@example.com")
    await _set_role(db_session, "rbac-lead@example.com", "team_lead")

    created = await client.post("/api/v1/teams", json={"name": "Leads"}, headers=headers)
    assert created.status_code == 201, created.text
    assert (await client.get("/api/v1/console/settings", headers=headers)).status_code == 403
    assert (await client.get("/api/v1/integrations", headers=headers)).status_code == 403
