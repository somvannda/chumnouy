"""Platform-operator surface: separate credential, cross-tenant read, quota edits."""
import uuid

import pytest
from sqlalchemy import select

from app.models import User

pytestmark = pytest.mark.asyncio


async def _signup(client, *, email, workspace="Acme Support"):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
    )
    assert signup.status_code == 201, signup.text
    token = signup.json()["token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _login(client, email):
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "supersecret123"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


async def _as_admin(client, db_session, email, role="admin"):
    """Flip a user to a platform role in the DB, then return signed-in headers."""
    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    user.platform_role = role
    await db_session.commit()
    return {"Authorization": f"Bearer {await _login(client, email)}"}


async def _api_key(client, headers, *, scopes):
    integration = await client.post(
        "/api/v1/integrations", json={"name": "POS", "scopes": scopes}, headers=headers
    )
    return (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]


async def test_admin_requires_a_platform_credential(client):
    _, headers = await _signup(client, email="plain@example.com")
    key = await _api_key(client, headers, scopes=["tickets:read"])

    # A normal console user is forbidden.
    assert (await client.get("/api/admin/usage", headers=headers)).status_code == 403
    # A tenant API key is not a console credential at all.
    assert (await client.get("/api/admin/usage", headers={"X-Api-Key": key})).status_code == 401
    assert (await client.get("/api/admin/usage")).status_code == 401


async def test_admin_lists_accounts_workspaces_and_usage(client, db_session):
    await _signup(client, email="admin@example.com", workspace="Admin WS")
    admin = await _as_admin(client, db_session, "admin@example.com")

    _, tenant_headers = await _signup(client, email="tenant@example.com", workspace="Tenant WS")
    key = await _api_key(client, tenant_headers, scopes=["tickets:read", "tickets:write"])
    await client.post(
        "/api/v1/tickets",
        json={"subject": "Hi", "message": "hello", "requester": {"external_id": "c1"}},
        headers={"X-Api-Key": key},
    )

    accounts = await client.get("/api/admin/accounts", headers=admin)
    assert accounts.status_code == 200, accounts.text
    assert {a["slug"] for a in accounts.json()} >= {"admin-ws", "tenant-ws"}
    assert all(a["workspace_count"] == 1 for a in accounts.json())

    workspaces = await client.get("/api/admin/workspaces?q=tenant", headers=admin)
    assert workspaces.status_code == 200
    assert [w["slug"] for w in workspaces.json()] == ["tenant-ws"]
    assert workspaces.json()[0]["ticket_count"] == 1

    usage = await client.get("/api/admin/usage", headers=admin)
    assert usage.status_code == 200
    body = usage.json()
    assert body["accounts"] == 2
    assert body["workspaces"] == 2
    assert body["tickets"] == 1
    assert body["open_tickets"] == 1


async def test_admin_can_read_and_update_a_workspace(client, db_session):
    await _signup(client, email="boss@example.com")
    admin = await _as_admin(client, db_session, "boss@example.com")
    workspace_id = (await client.get("/api/admin/workspaces", headers=admin)).json()[0]["id"]

    detail = await client.get(f"/api/admin/workspaces/{workspace_id}", headers=admin)
    assert detail.status_code == 200, detail.text
    assert detail.json()["member_count"] == 1
    assert detail.json()["knowledge_article_count"] > 0

    updated = await client.patch(
        f"/api/admin/workspaces/{workspace_id}",
        json={"is_active": False, "quota": {"tickets_per_month": 500}},
        headers=admin,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["is_active"] is False
    assert updated.json()["quota"] == {"tickets_per_month": 500}

    missing = await client.get(f"/api/admin/workspaces/{uuid.uuid4()}", headers=admin)
    assert missing.status_code == 404
