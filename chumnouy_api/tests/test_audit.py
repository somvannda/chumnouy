"""Audit log: ticket events as a filterable, workspace-scoped trail."""
import pytest

pytestmark = pytest.mark.asyncio


async def _workspace(client, *, email, workspace="Acme Support"):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
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


async def test_audit_lists_ticket_events(client):
    headers, key = await _workspace(client, email="audit@example.com")
    ticket_id = (
        await client.post(
            "/api/v1/tickets",
            json={"subject": "Audit me", "message": "hi", "requester": {"external_id": "c1"}},
            headers={"X-Api-Key": key},
        )
    ).json()["id"]
    await client.post(f"/api/v1/tickets/{ticket_id}/resolve", headers=headers)

    resp = await client.get("/api/v1/audit", headers=headers)
    assert resp.status_code == 200, resp.text
    types = [e["type"] for e in resp.json()["data"]]
    assert "ticket.created" in types and "ticket.resolved" in types
    assert all(e["ticket_id"] == ticket_id for e in resp.json()["data"])


async def test_audit_filters(client):
    headers, key = await _workspace(client, email="audit2@example.com")
    created = await client.post(
        "/api/v1/tickets",
        json={"subject": "Filtered", "message": "hi", "requester": {"external_id": "c1"}},
        headers={"X-Api-Key": key},
    )
    ticket_id = created.json()["id"]
    await client.post(f"/api/v1/tickets/{ticket_id}/resolve", headers=headers)

    by_type = await client.get("/api/v1/audit?type=ticket.resolved", headers=headers)
    assert [e["type"] for e in by_type.json()["data"]] == ["ticket.resolved"]

    by_actor = await client.get("/api/v1/audit?actor_type=user", headers=headers)
    assert by_actor.json()["data"] and all(e["actor_type"] == "user" for e in by_actor.json()["data"])

    limited = await client.get("/api/v1/audit?limit=1", headers=headers)
    assert len(limited.json()["data"]) == 1
    assert limited.json()["next_cursor"] is not None


async def test_audit_is_workspace_isolated(client):
    _, key_a = await _workspace(client, email="a@example.com", workspace="Workspace A")
    headers_b, _ = await _workspace(client, email="b@example.com", workspace="Workspace B")
    await client.post(
        "/api/v1/tickets",
        json={"subject": "A only", "message": "hi", "requester": {"external_id": "c1"}},
        headers={"X-Api-Key": key_a},
    )
    resp = await client.get("/api/v1/audit", headers=headers_b)
    assert resp.status_code == 200
    assert resp.json()["data"] == []
