"""Seat quota: a workspace can cap how many members it has."""
import pytest
from sqlalchemy import select

from app.models import Workspace

pytestmark = pytest.mark.asyncio


async def _workspace(client, *, email, seats=None):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": "Acme"},
    )
    assert signup.status_code == 201, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}
    return headers


async def _set_quota(db_session, seats):
    workspace = (await db_session.execute(select(Workspace))).scalars().first()
    workspace.settings = {**(workspace.settings or {}), "quota": {"seats": seats}}
    await db_session.commit()


async def _invite(client, headers, email):
    return await client.post(
        "/api/v1/members/invites", json={"email": email, "role": "agent"}, headers=headers
    )


async def test_invites_are_unlimited_without_a_quota(client):
    headers = await _workspace(client, email="seatfree@example.com")
    assert (await _invite(client, headers, "a@example.com")).status_code == 201
    assert (await _invite(client, headers, "b@example.com")).status_code == 201


async def test_seat_quota_blocks_further_invites(client, db_session):
    headers = await _workspace(client, email="seatcap@example.com")
    # The owner already occupies the only seat.
    await _set_quota(db_session, 1)

    blocked = await _invite(client, headers, "nope@example.com")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["message"] == "Seat quota reached"


async def test_seat_quota_allows_invites_within_the_limit(client, db_session):
    headers = await _workspace(client, email="seatsok@example.com")
    await _set_quota(db_session, 2)

    invited = await _invite(client, headers, "second@example.com")
    assert invited.status_code == 201, invited.text
    accepted = await client.post(
        "/api/v1/auth/invite/accept",
        json={"token": invited.json()["token"], "password": "supersecret123"},
    )
    assert accepted.status_code == 200, accepted.text

    # Now two active members: the third is refused.
    assert (await _invite(client, headers, "third@example.com")).status_code == 409
