"""SLA: due dates on create, policy override, breach sweep + event."""
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
