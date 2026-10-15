"""Triggers: conditions, actions, CRUD, scope and tenancy."""
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


def _trigger(**overrides):
    payload = {
        "name": "Escalate hardware",
        "event": "ticket.created",
        "conditions": [{"field": "tag", "op": "is", "value": "hardware"}],
        "actions": [
            {"type": "set_priority", "value": "high"},
            {"type": "add_tag", "value": "triaged"},
        ],
    }
    payload.update(overrides)
    return payload


def _ticket(tags=None):
    return {
        "subject": "Card reader",
        "message": "hi",
        "requester": {"external_id": "c1"},
        "tags": tags or [],
    }


async def test_trigger_applies_actions_on_create(client):
    headers, key = await _workspace(client, email="triggers@example.com")
    created = await client.post("/api/v1/triggers", json=_trigger(), headers=headers)
    assert created.status_code == 201, created.text

    ticket = await client.post("/api/v1/tickets", json=_ticket(["hardware"]), headers={"X-Api-Key": key})
    assert ticket.status_code == 201, ticket.text
    body = ticket.json()
    assert body["priority"] == "high"
    assert "triaged" in body["tags"]

    audit = await client.get("/api/v1/audit?type=trigger.applied", headers=headers)
    assert audit.json()["data"]


async def test_trigger_does_not_match_leaves_the_ticket(client):
    headers, key = await _workspace(client, email="triggers2@example.com")
    await client.post("/api/v1/triggers", json=_trigger(), headers=headers)

    ticket = await client.post("/api/v1/tickets", json=_ticket(["billing"]), headers={"X-Api-Key": key})
    assert ticket.json()["priority"] == "normal"
    assert "triaged" not in ticket.json()["tags"]
    assert (await client.get("/api/v1/audit?type=trigger.applied", headers=headers)).json()["data"] == []


async def test_trigger_crud(client):
    headers, _ = await _workspace(client, email="triggers3@example.com")
    created = await client.post("/api/v1/triggers", json=_trigger(), headers=headers)
    trigger_id = created.json()["id"]

    listed = await client.get("/api/v1/triggers", headers=headers)
    assert [t["id"] for t in listed.json()] == [trigger_id]

    fetched = await client.get(f"/api/v1/triggers/{trigger_id}", headers=headers)
    assert fetched.json()["event"] == "ticket.created"

    patched = await client.patch(
        f"/api/v1/triggers/{trigger_id}", json={"is_active": False}, headers=headers
    )
    assert patched.json()["is_active"] is False

    deleted = await client.delete(f"/api/v1/triggers/{trigger_id}", headers=headers)
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/triggers", headers=headers)).json() == []


async def test_triggers_require_write_scope_and_are_isolated(client):
    _, read_key = await _workspace(client, email="triggers4@example.com", scopes=("tickets:read",))
    denied = await client.post("/api/v1/triggers", json=_trigger(), headers={"X-Api-Key": read_key})
    assert denied.status_code == 403

    headers_a, _ = await _workspace(client, email="a@example.com", workspace="Workspace A")
    headers_b, _ = await _workspace(client, email="b@example.com", workspace="Workspace B")
    trigger_id = (
        await client.post("/api/v1/triggers", json=_trigger(), headers=headers_a)
    ).json()["id"]
    assert (await client.get("/api/v1/triggers", headers=headers_b)).json() == []
    assert (await client.get(f"/api/v1/triggers/{trigger_id}", headers=headers_b)).status_code == 404
