"""SLA: due dates on create, policy override, breach sweep + event."""
from datetime import datetime

import pytest
from sqlalchemy import select

from app.models import WebhookDelivery
from app.services import sla as sla_svc

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


def _body(priority="normal"):
    return {"subject": "Hi", "message": "hello", "requester": {"external_id": "c1"}, "priority": priority}


async def test_ticket_gets_sla_due_dates(client):
    _, key = await _workspace(client, email="sla@example.com")
    created = await client.post("/api/v1/tickets", json=_body("urgent"), headers={"X-Api-Key": key})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["first_response_due_at"] is not None
    assert body["resolution_due_at"] is not None
    assert body["sla_breached_at"] is None


async def test_policy_is_configurable(client):
    headers, _ = await _workspace(client, email="slapolicy@example.com")
    settings = await client.get("/api/v1/console/settings", headers=headers)
    assert "normal" in settings.json()["sla"]["resolution_minutes"]

    updated = await client.patch(
        "/api/v1/console/settings/sla",
        json={"resolution_minutes": {"normal": 5}},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["sla"]["resolution_minutes"]["normal"] == 5


async def test_breach_sweep_marks_and_raises_event(client, db_session):
    headers, key = await _workspace(client, email="slabreach@example.com")
    await client.post(
        "/api/v1/webhooks",
        json={"url": "https://example.com/hook", "events": ["sla.breached"]},
        headers=headers,
    )
    await client.patch(
        "/api/v1/console/settings/sla", json={"resolution_minutes": {"normal": 0}}, headers=headers
    )
    created = await client.post("/api/v1/tickets", json=_body(), headers={"X-Api-Key": key})
    ticket_id = created.json()["id"]

    swept = await sla_svc.sweep_breaches(db_session)
    assert swept == 1

    detail = await client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert detail.json()["sla_breached_at"] is not None

    audit = await client.get("/api/v1/audit?type=sla.breached", headers=headers)
    assert [e["ticket_id"] for e in audit.json()["data"]] == [ticket_id]

    db_session.expire_all()
    deliveries = (await db_session.execute(select(WebhookDelivery))).scalars().all()
    assert any(d.event == "sla.breached" for d in deliveries)

    # The sweep is idempotent.
    assert await sla_svc.sweep_breaches(db_session) == 0


def _minutes_between(body, field="first_response_due_at"):
    created = datetime.fromisoformat(body["created_at"])
    due = datetime.fromisoformat(body[field])
    return round((due - created).total_seconds() / 60)


async def test_per_team_sla_overrides_workspace_policy(client):
    headers, key = await _workspace(client, email="slateam@example.com")
    team_id = (
        await client.post("/api/v1/teams", json={"name": "Billing"}, headers=headers)
    ).json()["id"]

    updated = await client.patch(
        "/api/v1/console/settings/sla",
        json={"teams": {team_id: {"first_response_minutes": {"normal": 5}}}},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["sla"]["teams"][team_id]["first_response_minutes"] == {"normal": 5}
    # Only the override is stored; the workspace policy is untouched.
    assert updated.json()["sla"]["first_response_minutes"]["normal"] == 240

    created = await client.post("/api/v1/tickets", json=_body(), headers={"X-Api-Key": key})
    ticket_id = created.json()["id"]
    assert _minutes_between(created.json()) == 240

    # Assigning the team re-stamps the targets from the team policy.
    assigned = await client.patch(
        f"/api/v1/tickets/{ticket_id}", json={"team_id": team_id}, headers=headers
    )
    assert _minutes_between(assigned.json()) == 5
    # Priorities the team did not override still follow the workspace policy.
    assert _minutes_between(assigned.json(), "resolution_due_at") == 2880


async def test_clearing_the_team_restores_the_workspace_policy(client):
    headers, key = await _workspace(client, email="slaclear@example.com")
    team_id = (
        await client.post("/api/v1/teams", json={"name": "Support"}, headers=headers)
    ).json()["id"]
    await client.patch(
        "/api/v1/console/settings/sla",
        json={"teams": {team_id: {"first_response_minutes": {"normal": 1}}}},
        headers=headers,
    )
    ticket_id = (
        await client.post("/api/v1/tickets", json=_body(), headers={"X-Api-Key": key})
    ).json()["id"]

    await client.patch(f"/api/v1/tickets/{ticket_id}", json={"team_id": team_id}, headers=headers)
    cleared = await client.patch(
        f"/api/v1/tickets/{ticket_id}", json={"clear_team": True}, headers=headers
    )
    assert cleared.json()["team_id"] is None
    assert _minutes_between(cleared.json()) == 240


async def test_sla_team_overrides_drop_bad_keys_and_values(client):
    headers, _ = await _workspace(client, email="slasafe@example.com")
    updated = await client.patch(
        "/api/v1/console/settings/sla",
        json={
            "teams": {
                "not-a-uuid": {"first_response_minutes": {"normal": 3}},
                "11111111-1111-1111-1111-111111111111": {
                    "first_response_minutes": {"normal": 7, "bogus": 9}
                },
            }
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["sla"]["teams"] == {
        "11111111-1111-1111-1111-111111111111": {
            "first_response_minutes": {"normal": 7},
            "resolution_minutes": {},
        }
    }
