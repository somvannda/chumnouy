"""Macros: CRUD and apply-on-demand."""
import pytest

pytestmark = pytest.mark.asyncio


async def _workspace(client, *, email, workspace="Acme", scopes=("tickets:read", "tickets:write")):
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


def _macro(**overrides):
    payload = {
        "name": "Escalate",
        "actions": [
            {"type": "set_priority", "value": "high"},
            {"type": "add_tag", "value": "escalated"},
        ],
    }
    payload.update(overrides)
    return payload


async def _ticket(client, key):
    return (
        await client.post(
            "/api/v1/tickets",
            json={"subject": "Hi", "message": "hello", "requester": {"external_id": "c1"}},
            headers={"X-Api-Key": key},
        )
    ).json()["id"]


async def test_macro_crud_and_apply(client):
    headers, key = await _workspace(client, email="macros@example.com")
    created = await client.post("/api/v1/macros", json=_macro(), headers=headers)
    assert created.status_code == 201, created.text
    macro_id = created.json()["id"]

    listed = await client.get("/api/v1/macros", headers=headers)
    assert [m["id"] for m in listed.json()] == [macro_id]

    ticket_id = await _ticket(client, key)
    applied = await client.post(f"/api/v1/tickets/{ticket_id}/macros/{macro_id}", headers=headers)
    assert applied.status_code == 200, applied.text
    assert applied.json()["priority"] == "high"
    assert "escalated" in applied.json()["tags"]

    audit = await client.get("/api/v1/audit?type=macro.applied", headers=headers)
    assert [e["ticket_id"] for e in audit.json()["data"]] == [ticket_id]

    patched = await client.patch(
        f"/api/v1/macros/{macro_id}", json={"name": "Escalate fast"}, headers=headers
    )
    assert patched.json()["name"] == "Escalate fast"

    assert (await client.delete(f"/api/v1/macros/{macro_id}", headers=headers)).status_code == 204
    assert (await client.get("/api/v1/macros", headers=headers)).json() == []


async def test_macro_requires_write_scope(client):
    _, key = await _workspace(client, email="macros2@example.com", scopes=("tickets:read",))
    denied = await client.post("/api/v1/macros", json=_macro(), headers={"X-Api-Key": key})
    assert denied.status_code == 403


async def test_macros_are_workspace_isolated(client):
    headers_a, key_a = await _workspace(client, email="a@example.com", workspace="Workspace A")
    headers_b, _ = await _workspace(client, email="b@example.com", workspace="Workspace B")
    macro_id = (
        await client.post("/api/v1/macros", json=_macro(), headers=headers_a)
    ).json()["id"]
    ticket_id = await _ticket(client, key_a)

    assert (await client.get("/api/v1/macros", headers=headers_b)).json() == []
    assert (
        await client.post(f"/api/v1/tickets/{ticket_id}/macros/{macro_id}", headers=headers_b)
    ).status_code == 404
