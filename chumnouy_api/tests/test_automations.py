"""Time-based automations: due tickets get the actions, once."""
import pytest

from app.services import automations as svc

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


async def _ticket(client, key, tags=None):
    resp = await client.post(
        "/api/v1/tickets",
        json={
            "subject": "Stale",
            "message": "hi",
            "requester": {"external_id": "c1"},
            "tags": tags or [],
        },
        headers={"X-Api-Key": key},
    )
    return resp.json()["id"]


def _automation(**overrides):
    payload = {
        "name": "Nudge stale billing",
        "after_minutes": 0,
        "conditions": [{"field": "tag", "op": "is", "value": "billing"}],
        "actions": [{"type": "add_tag", "value": "stale"}],
    }
    payload.update(overrides)
    return payload


async def test_automation_applies_once(client, db_session):
    headers, key = await _workspace(client, email="automations@example.com")
    await client.post("/api/v1/automations", json=_automation(), headers=headers)
    ticket_id = await _ticket(client, key, ["billing"])

    assert await svc.sweep_automations(db_session) == 1

    detail = await client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert "stale" in detail.json()["tags"]
    audit = await client.get("/api/v1/audit?type=automation.applied", headers=headers)
    assert [e["ticket_id"] for e in audit.json()["data"]] == [ticket_id]

    # Idempotent: the automation is not applied again.
    assert await svc.sweep_automations(db_session) == 0


async def test_automation_respects_conditions(client, db_session):
    headers, key = await _workspace(client, email="automations2@example.com")
    await client.post("/api/v1/automations", json=_automation(), headers=headers)
    ticket_id = await _ticket(client, key, ["hardware"])

    assert await svc.sweep_automations(db_session) == 0
    detail = await client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert "stale" not in detail.json()["tags"]


async def test_automation_crud(client):
    headers, _ = await _workspace(client, email="automations3@example.com")
    created = await client.post("/api/v1/automations", json=_automation(), headers=headers)
    assert created.status_code == 201, created.text
    automation_id = created.json()["id"]

    listed = await client.get("/api/v1/automations", headers=headers)
    assert [a["id"] for a in listed.json()] == [automation_id]

    patched = await client.patch(
        f"/api/v1/automations/{automation_id}", json={"is_active": False}, headers=headers
    )
    assert patched.json()["is_active"] is False

    assert (await client.delete(f"/api/v1/automations/{automation_id}", headers=headers)).status_code == 204
