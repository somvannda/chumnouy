"""Data retention: resolved tickets are purged after the configured window."""
from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import Ticket, utcnow
from app.services import retention as retention_svc

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


async def _ticket(client, key, external_id="c1"):
    created = await client.post(
        "/api/v1/tickets",
        json={"subject": "Hi", "message": "hello", "requester": {"external_id": external_id}},
        headers={"X-Api-Key": key},
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def _backdate_resolved(db_session, ticket_id, *, days):
    ticket = (
        await db_session.execute(select(Ticket).where(Ticket.id == UUID(str(ticket_id))))
    ).scalar_one()
    ticket.resolved_at = utcnow() - timedelta(days=days)
    await db_session.commit()


async def _load_ticket(db_session, ticket_id):
    return (
        await db_session.execute(select(Ticket).where(Ticket.id == UUID(str(ticket_id))))
    ).scalar_one()


async def test_nothing_is_purged_without_a_window(client, db_session):
    headers, key = await _workspace(client, email="retentionoff@example.com")
    ticket_id = await _ticket(client, key)
    await client.post(f"/api/v1/tickets/{ticket_id}/resolve", headers=headers)
    await _backdate_resolved(db_session, ticket_id, days=30)

    assert await retention_svc.purge(db_session) == 0
    assert (await client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)).status_code == 200


async def test_resolved_tickets_past_the_window_are_purged(client, db_session):
    headers, key = await _workspace(client, email="retentionon@example.com")
    updated = await client.patch(
        "/api/v1/console/settings/retention", json={"days": 7}, headers=headers
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["retention"]["days"] == 7

    old = await _ticket(client, key, "old")
    recent = await _ticket(client, key, "recent")
    for ticket_id, days in ((old, 30), (recent, 1)):
        await client.post(f"/api/v1/tickets/{ticket_id}/resolve", headers=headers)
        await _backdate_resolved(db_session, ticket_id, days=days)

    assert await retention_svc.purge(db_session) == 1
    assert (await client.get(f"/api/v1/tickets/{old}", headers=headers)).status_code == 404
    assert (await client.get(f"/api/v1/tickets/{recent}", headers=headers)).status_code == 200

    # Idempotent: nothing left to purge.
    assert await retention_svc.purge(db_session) == 0


async def test_open_tickets_are_never_purged(client, db_session):
    headers, key = await _workspace(client, email="retentionopen@example.com")
    await client.patch("/api/v1/console/settings/retention", json={"days": 1}, headers=headers)

    ticket_id = await _ticket(client, key)
    ticket = await _load_ticket(db_session, ticket_id)
    # Long-lived but still open.
    ticket.created_at = utcnow() - timedelta(days=365)
    await db_session.commit()

    assert await retention_svc.purge(db_session) == 0
    assert (await client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)).status_code == 200


async def test_retention_window_is_audited_and_can_be_cleared(client):
    headers, _ = await _workspace(client, email="retentionaudit@example.com")
    await client.patch("/api/v1/console/settings/retention", json={"days": 30}, headers=headers)
    await client.patch("/api/v1/console/settings/retention", json={"days": 0}, headers=headers)

    settings = (await client.get("/api/v1/console/settings", headers=headers)).json()
    assert settings["retention"]["days"] == 0

    events = (
        await client.get("/api/v1/audit/workspace?type=settings.retention", headers=headers)
    ).json()["data"]
    assert [event["data"]["days"] for event in events] == [0, 30]


async def test_purge_only_touches_workspaces_with_a_window(client, db_session):
    headers_a, key_a = await _workspace(client, email="retentiona@example.com")
    headers_b, key_b = await _workspace(client, email="retentionb@example.com")
    await client.patch("/api/v1/console/settings/retention", json={"days": 1}, headers=headers_a)

    # Workspace B never enabled retention, so its resolved ticket survives.
    ticket_b = await _ticket(client, key_b, "b1")
    await client.post(f"/api/v1/tickets/{ticket_b}/resolve", headers=headers_b)
    await _backdate_resolved(db_session, ticket_b, days=30)

    ticket_a = await _ticket(client, key_a, "a1")
    await client.post(f"/api/v1/tickets/{ticket_a}/resolve", headers=headers_a)
    await _backdate_resolved(db_session, ticket_a, days=30)

    assert await retention_svc.purge(db_session) == 1
    assert (await client.get(f"/api/v1/tickets/{ticket_a}", headers=headers_a)).status_code == 404
    assert (await client.get(f"/api/v1/tickets/{ticket_b}", headers=headers_b)).status_code == 200
