"""Custom webhook actions: a trigger/automation can call a workspace webhook."""
import pytest
from sqlalchemy import select

from app.models import WebhookDelivery

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


async def _webhook(client, headers, *, events=(), url="https://example.com/hook"):
    response = await client.post(
        "/api/v1/webhooks", json={"url": url, "events": list(events)}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["webhook"]


async def _ticket(client, key, external_id="c1"):
    response = await client.post(
        "/api/v1/tickets",
        json={"subject": "Hi", "message": "hello", "requester": {"external_id": external_id}},
        headers={"X-Api-Key": key},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_trigger_webhook_action_queues_a_delivery(client, db_session):
    headers, key = await _workspace(client, email="webhookaction@example.com")
    # Deliberately subscribe to *nothing*: an explicit action still calls it.
    hook = await _webhook(client, headers)

    created = await client.post(
        "/api/v1/triggers",
        json={
            "name": "Call the POS",
            "event": "ticket.created",
            "conditions": [],
            "actions": [{"type": "webhook", "value": hook["id"]}],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text

    ticket_id = await _ticket(client, key)
    deliveries = (await db_session.execute(select(WebhookDelivery))).scalars().all()
    assert len(deliveries) == 1
    delivery = deliveries[0]
    assert delivery.event == "action.webhook"
    assert delivery.payload["data"]["source"] == "trigger:Call the POS"
    assert delivery.payload["ticket"]["id"] == ticket_id
    assert delivery.status == "pending"

    audit = await client.get("/api/v1/audit?type=trigger.applied", headers=headers)
    assert audit.json()["data"][0]["data"]["changes"] == [f"webhook={hook['id']}"]


async def test_webhook_action_ignores_inactive_and_unknown_targets(client, db_session):
    headers, key = await _workspace(client, email="webhookbad@example.com")
    hook = await _webhook(client, headers)
    await client.delete(f"/api/v1/webhooks/{hook['id']}", headers=headers)

    await client.post(
        "/api/v1/triggers",
        json={
            "name": "Nothing happens",
            "event": "ticket.created",
            "conditions": [],
            "actions": [
                {"type": "webhook", "value": hook["id"]},
                {"type": "webhook", "value": "not-a-uuid"},
                {"type": "webhook", "value": "11111111-1111-1111-1111-111111111111"},
            ],
        },
        headers=headers,
    )
    await _ticket(client, key)
    assert (await db_session.execute(select(WebhookDelivery))).scalars().all() == []


async def test_webhook_action_is_workspace_scoped(client, db_session):
    headers_a, _ = await _workspace(client, email="hooka@example.com")
    headers_b, key_b = await _workspace(client, email="hookb@example.com")
    foreign = await _webhook(client, headers_a, url="https://a.example.com/hook")

    # Workspace B points at workspace A's webhook id: the action must not deliver.
    await client.post(
        "/api/v1/triggers",
        json={
            "name": "Foreign",
            "event": "ticket.created",
            "conditions": [],
            "actions": [{"type": "webhook", "value": foreign["id"]}],
        },
        headers=headers_b,
    )
    await _ticket(client, key_b, "b1")
    assert (await db_session.execute(select(WebhookDelivery))).scalars().all() == []
