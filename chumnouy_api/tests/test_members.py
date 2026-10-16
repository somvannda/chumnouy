"""Workspace members and invitations."""
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import WorkspaceInvite, utcnow

pytestmark = pytest.mark.asyncio

PASSWORD = "supersecret123"


async def _signup(client, email):
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": PASSWORD, "name": "Owner", "workspace_name": "Acme"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def _invite(client, headers, **payload):
    body = {"email": payload.pop("email"), "role": payload.pop("role", "agent")}
    body.update(payload)
    return await client.post("/api/v1/members/invites", json=body, headers=headers)


async def _join(client, headers, email, role="agent", name=None):
    """Invite someone new and accept as them; returns their console headers."""
    invited = await _invite(client, headers, email=email, role=role, **({"name": name} if name else {}))
    assert invited.status_code == 201, invited.text
    accepted = await client.post(
        "/api/v1/auth/invite/accept",
        json={"token": invited.json()["token"], "password": PASSWORD, "name": name or email},
    )
    assert accepted.status_code == 200, accepted.text
    return {"Authorization": f"Bearer {accepted.json()['token']}"}


async def test_invite_new_member_and_accept(client):
    headers = await _signup(client, "invite-owner@example.com")

    invited = await _invite(client, headers, email="New.Person@example.com", name="New Person")
    assert invited.status_code == 201, invited.text
    body = invited.json()
    assert body["status"] == "pending"
    assert body["role"] == "agent"
    assert body["token"].startswith("inv_")

    # The token is shown once; the listing only ever exposes the pending state.
    listed = (await client.get("/api/v1/members/invites", headers=headers)).json()
    assert [row["email"] for row in listed] == ["new.person@example.com"]
    assert listed[0]["token"] is None

    accepted = await client.post(
        "/api/v1/auth/invite/accept",
        json={"token": body["token"], "password": PASSWORD, "name": "New Person"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["workspace"]["role"] == "agent"
    assert accepted.json()["user"]["email"] == "new.person@example.com"

    login = await client.post(
        "/api/v1/auth/login", json={"email": "new.person@example.com", "password": PASSWORD}
    )
    assert login.status_code == 200, login.text

    roster = (await client.get("/api/v1/members", headers=headers)).json()
    assert sorted(member["email"] for member in roster) == [
        "invite-owner@example.com",
        "new.person@example.com",
    ]

    # Single use.
    again = await client.post(
        "/api/v1/auth/invite/accept", json={"token": body["token"], "password": PASSWORD}
    )
    assert again.status_code == 400


async def test_invite_existing_user_joins_immediately(client):
    headers = await _signup(client, "existing-owner@example.com")
    await _signup(client, "already@example.com")

    joined = await _invite(client, headers, email="already@example.com", role="team_lead")
    assert joined.status_code == 201, joined.text
    assert joined.json()["status"] == "accepted"
    assert joined.json()["token"] is None

    roster = (await client.get("/api/v1/members", headers=headers)).json()
    assert {member["email"]: member["role"] for member in roster}["already@example.com"] == "team_lead"

    duplicate = await _invite(client, headers, email="already@example.com")
    assert duplicate.status_code == 400
    assert "already a member" in duplicate.json()["error"]["message"]


async def test_pending_invite_conflict_and_revoke(client):
    headers = await _signup(client, "revoke-owner@example.com")
    first = await _invite(client, headers, email="pending@example.com")
    assert first.status_code == 201

    duplicate = await _invite(client, headers, email="pending@example.com")
    assert duplicate.status_code == 400
    assert "pending invitation" in duplicate.json()["error"]["message"]

    revoked = await client.delete(
        f"/api/v1/members/invites/{first.json()['id']}", headers=headers
    )
    assert revoked.status_code == 204
    assert (await client.get("/api/v1/members/invites", headers=headers)).json() == []

    # Revoking frees the address for a fresh invitation.
    reissued = await _invite(client, headers, email="pending@example.com")
    assert reissued.status_code == 201
    assert reissued.json()["token"] != first.json()["token"]


async def test_expired_invite_is_rejected(client, db_session):
    headers = await _signup(client, "expiry-owner@example.com")
    invited = await _invite(client, headers, email="late@example.com")

    row = (await db_session.execute(select(WorkspaceInvite))).scalars().first()
    row.expires_at = utcnow() - timedelta(days=1)
    await db_session.commit()

    late = await client.post(
        "/api/v1/auth/invite/accept", json={"token": invited.json()["token"], "password": PASSWORD}
    )
    assert late.status_code == 400
    assert "expired" in late.json()["error"]["message"]


async def test_role_change_and_owner_protection(client):
    headers = await _signup(client, "roles-owner@example.com")
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    owner_id = me["user"]["id"]

    member_headers = await _join(client, headers, "role-agent@example.com")
    agent_id = (await client.get("/api/v1/auth/me", headers=member_headers)).json()["user"]["id"]

    promoted = await client.patch(
        f"/api/v1/members/{agent_id}", json={"role": "admin"}, headers=headers
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["role"] == "admin"

    demote_owner = await client.patch(
        f"/api/v1/members/{owner_id}", json={"role": "agent"}, headers=headers
    )
    assert demote_owner.status_code == 400
    assert "owner" in demote_owner.json()["error"]["message"]

    remove_owner = await client.delete(f"/api/v1/members/{owner_id}", headers=headers)
    assert remove_owner.status_code == 400

    # An admin cannot remove themselves (that would strand the workspace).
    self_remove = await client.delete(f"/api/v1/members/{agent_id}", headers=member_headers)
    assert self_remove.status_code == 400
    assert "yourself" in self_remove.json()["error"]["message"]

    removed = await client.delete(f"/api/v1/members/{agent_id}", headers=headers)
    assert removed.status_code == 204
    roster = (await client.get("/api/v1/members", headers=headers)).json()
    assert [member["email"] for member in roster] == ["roles-owner@example.com"]


async def test_members_rbac(client):
    headers = await _signup(client, "rbac-owner@example.com")
    agent_headers = await _join(client, headers, "rbac-agent@example.com")

    # An agent can read the roster but cannot manage it.
    assert (await client.get("/api/v1/members", headers=agent_headers)).status_code == 200
    forbidden = await _invite(client, agent_headers, email="sneaky@example.com")
    assert forbidden.status_code == 403

    unknown = await client.post(
        "/api/v1/auth/invite/accept", json={"token": "inv_not-a-real-token", "password": PASSWORD}
    )
    assert unknown.status_code == 404
