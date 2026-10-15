"""Per-workspace monthly ticket quotas."""
import pytest
from sqlalchemy import select

from app.models import Workspace

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
    return headers, key


async def _set_quota(db_session, limit):
    workspace = (await db_session.execute(select(Workspace))).scalars().first()
    workspace.settings = {**(workspace.settings or {}), "quota": {"tickets_per_month": limit}}
    await db_session.commit()


def _body(external_id="c1"):
    return {"subject": "Hi", "message": "hello", "requester": {"external_id": external_id}}


async def test_ticket_quota_is_enforced(client, db_session):
    _, key = await _workspace(client, email="quota@example.com")
    await _set_quota(db_session, 1)

    first = await client.post("/api/v1/tickets", json=_body(), headers={"X-Api-Key": key})
    assert first.status_code == 201, first.text

    second = await client.post("/api/v1/tickets", json=_body("c2"), headers={"X-Api-Key": key})
    assert second.status_code == 429, second.text
    assert second.json()["error"]["code"] == "too_many_requests"


async def test_no_quota_means_unlimited(client, db_session):
    _, key = await _workspace(client, email="unlimited@example.com")
    for i in range(3):
        resp = await client.post("/api/v1/tickets", json=_body(f"c{i}"), headers={"X-Api-Key": key})
        assert resp.status_code == 201, resp.text


async def test_public_create_respects_quota(client, db_session):
    headers, key = await _workspace(client, email="publicquota@example.com")
    await _set_quota(db_session, 1)
    await client.post("/api/v1/tickets", json=_body(), headers={"X-Api-Key": key})

    requester = (await client.get("/api/v1/requesters?q=c1", headers=headers)).json()[0]
    token = (
        await client.post(f"/api/v1/requesters/{requester['id']}/portal-token", headers=headers)
    ).json()["token"]
    resp = await client.post(
        "/api/v1/public/tickets",
        json={"subject": "More", "message": "hi"},
        headers={"X-Requester-Token": token},
    )
    assert resp.status_code == 429, resp.text
