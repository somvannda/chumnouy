"""Bulk ticket actions: apply, scope, isolation."""
import pytest

pytestmark = pytest.mark.asyncio


async def _workspace(client, *, email, workspace="Acme Support", scopes=("tickets:read", "tickets:write")):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
    )
    assert signup.status_code == 201, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}
    integration = await client.post(
        "/api/v1/integrations", json={"name": "POS", "scopes": list(scopes)}, headers=headers
    )
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]
    return headers, key


async def _ticket(client, key, external_id="c1"):
    resp = await client.post(
        "/api/v1/tickets",
        json={"subject": "Hi", "message": "hello", "requester": {"external_id": external_id}},
        headers={"X-Api-Key": key},
    )
    return resp.json()["id"]


async def test_bulk_update_status_and_tags(client):
    headers, key = await _workspace(client, email="bulk@example.com")
    first = await _ticket(client, key, "c1")
    second = await _ticket(client, key, "c2")

    resp = await client.post(
        "/api/v1/console/bulk",
        json={"ticket_ids": [first, second], "action": {"status": "resolved", "add_tags": ["bulk"]}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated"] == 2

    detail = await client.get(f"/api/v1/tickets/{first}", headers=headers)
    assert detail.json()["status"] == "resolved"
    assert "bulk" in detail.json()["tags"]

    audit = await client.get("/api/v1/audit?type=ticket.updated", headers=headers)
    assert any(e["data"].get("bulk") for e in audit.json()["data"])


async def test_bulk_requires_write_scope(client):
    _, key = await _workspace(client, email="bulk2@example.com", scopes=("tickets:read",))
    denied = await client.post(
        "/api/v1/console/bulk",
        json={"ticket_ids": ["11111111-1111-1111-1111-111111111111"], "action": {"status": "open"}},
        headers={"X-Api-Key": key},
    )
    assert denied.status_code == 403


async def test_bulk_is_workspace_isolated(client):
    headers_a, key_a = await _workspace(client, email="a@example.com", workspace="Workspace A")
    _, key_b = await _workspace(client, email="b@example.com", workspace="Workspace B")
    foreign = await _ticket(client, key_b, "c9")

    resp = await client.post(
        "/api/v1/console/bulk",
        json={"ticket_ids": [foreign], "action": {"status": "resolved"}},
        headers=headers_a,
    )
    assert resp.json()["updated"] == 0
