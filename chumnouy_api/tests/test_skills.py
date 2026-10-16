"""Skill-aware routing: member skills, ticket required_skills, skill strategy."""
import pytest
from sqlalchemy import select

from app.models import Membership, User, Workspace

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
        json={"name": "POS", "scopes": ["tickets:read", "tickets:write"]},
        headers=headers,
    )
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]
    return headers, key


async def _agent(db_session, workspace_id, email, skills=None):
    user = User(email=email, password_hash="x", name=email.split("@")[0])
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        Membership(
            workspace_id=workspace_id,
            user_id=user.id,
            role="agent",
            skills=list(skills or []),
        )
    )
    await db_session.commit()
    return str(user.id)


async def _ticket(client, key, *, external_id="c1", required_skills=None):
    body = {"subject": "Hi", "message": "hello", "requester": {"external_id": external_id}}
    if required_skills is not None:
        body["required_skills"] = required_skills
    response = await client.post("/api/v1/tickets", json=body, headers={"X-Api-Key": key})
    assert response.status_code == 201, response.text
    return response.json()


async def _workspace_id(db_session):
    return (await db_session.execute(select(Workspace))).scalars().first().id


async def test_skills_round_trip_on_members_and_tickets(client, db_session):
    headers, key = await _workspace(client, email="skills@example.com")
    workspace_id = await _workspace_id(db_session)
    agent = await _agent(db_session, workspace_id, "skilled@example.com")

    updated = await client.patch(
        f"/api/v1/members/{agent}",
        json={"skills": ["Billing", "billing ", "  ", "Refunds", "x" * 60]},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    skills = updated.json()["skills"]
    assert skills[:2] == ["billing", "refunds"]
    assert len(skills) == 3  # the duplicate and the blank were dropped
    assert all(len(skill) <= 40 for skill in skills)

    roster = (await client.get("/api/v1/members", headers=headers)).json()
    assert {m["user_id"]: m["skills"] for m in roster}[agent] == skills

    ticket = await _ticket(client, key, required_skills=["Billing"])
    assert ticket["required_skills"] == ["Billing"]

    changed = await client.patch(
        f"/api/v1/tickets/{ticket['id']}", json={"required_skills": ["refunds"]}, headers=headers
    )
    assert changed.json()["required_skills"] == ["refunds"]

    cleared = await client.patch(
        f"/api/v1/tickets/{ticket['id']}", json={"required_skills": []}, headers=headers
    )
    assert cleared.json()["required_skills"] == []


async def test_skill_routing_prefers_a_matching_agent(client, db_session):
    headers, key = await _workspace(client, email="skillroute@example.com")
    workspace_id = await _workspace_id(db_session)
    await _agent(db_session, workspace_id, "generalist@example.com")
    billing = await _agent(db_session, workspace_id, "billing@example.com", skills=["billing"])

    ticket = await _ticket(client, key, required_skills=["billing"])
    assigned = await client.post(
        f"/api/v1/tickets/{ticket['id']}/assign", json={"strategy": "skill"}, headers=headers
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assignee_user_id"] == billing


async def test_explicit_skill_overrides_the_ticket(client, db_session):
    headers, key = await _workspace(client, email="skillspec@example.com")
    workspace_id = await _workspace_id(db_session)
    refunds = await _agent(db_session, workspace_id, "refunds@example.com", skills=["refunds"])
    await _agent(db_session, workspace_id, "billing@example.com", skills=["billing"])

    ticket = await _ticket(client, key, required_skills=["billing"])
    assigned = await client.post(
        f"/api/v1/tickets/{ticket['id']}/assign",
        json={"strategy": "load_balanced", "skill": "Refunds"},
        headers=headers,
    )
    assert assigned.json()["assignee_user_id"] == refunds


async def test_routing_falls_back_when_nobody_has_the_skill(client, db_session):
    headers, key = await _workspace(client, email="skillfall@example.com")
    workspace_id = await _workspace_id(db_session)
    generalist = await _agent(db_session, workspace_id, "only@example.com", skills=["billing"])

    team_id = (
        await client.post("/api/v1/teams", json={"name": "Tier 1"}, headers=headers)
    ).json()["id"]
    await client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"user_id": generalist, "role": "member"},
        headers=headers,
    )

    # The only candidate in the team lacks the skill; better to assign them than
    # to leave the ticket unowned.
    ticket = await _ticket(client, key, required_skills=["legal"])
    assigned = await client.post(
        f"/api/v1/tickets/{ticket['id']}/assign",
        json={"strategy": "skill", "team_id": team_id},
        headers=headers,
    )
    assert assigned.json()["assignee_user_id"] == generalist


async def test_skill_routing_can_be_scoped_to_a_team(client, db_session):
    headers, key = await _workspace(client, email="skillteam@example.com")
    workspace_id = await _workspace_id(db_session)
    outside = await _agent(db_session, workspace_id, "outside@example.com", skills=["billing"])
    inside = await _agent(db_session, workspace_id, "inside@example.com", skills=["billing"])

    team_id = (
        await client.post("/api/v1/teams", json={"name": "Billing"}, headers=headers)
    ).json()["id"]
    await client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"user_id": inside, "role": "member"},
        headers=headers,
    )

    ticket = await _ticket(client, key, required_skills=["billing"])
    assigned = await client.post(
        f"/api/v1/tickets/{ticket['id']}/assign",
        json={"strategy": "skill", "team_id": team_id},
        headers=headers,
    )
    assert assigned.json()["assignee_user_id"] == inside
    assert assigned.json()["team_id"] == team_id
    assert assigned.json()["assignee_user_id"] != outside
