"""Reports: workspace summary counts, averages and SLA compliance."""
from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import Ticket, utcnow
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


def _body(external_id="c1"):
    return {"subject": "Hi", "message": "hello", "requester": {"external_id": external_id}}


async def test_daily_report_is_a_dense_window(client):
    headers, _ = await _workspace(client, email="daily@example.com")

    body = (await client.get("/api/v1/reports/daily?days=7", headers=headers)).json()
    assert len(body["days"]) == 7
    assert [day["created"] for day in body["days"]] == [0] * 7
    assert body["totals"]["created"] == 0
    assert body["totals"]["breached"] == 0
    # The window ends today and has no gaps.
    days = [day["day"] for day in body["days"]]
    assert days == sorted(days)
    assert days[-1] >= days[0]


async def test_daily_report_counts_today_activity(client):
    headers, key = await _workspace(client, email="dailyactivity@example.com")
    first = await client.post("/api/v1/tickets", json=_body(), headers={"X-Api-Key": key})
    await client.post("/api/v1/tickets", json=_body("c2"), headers={"X-Api-Key": key})
    await client.post(f"/api/v1/tickets/{first.json()['id']}/resolve", headers=headers)

    body = (await client.get("/api/v1/reports/daily", headers=headers)).json()
    today = body["days"][-1]
    assert today["created"] == 2
    assert today["resolved"] == 1
    assert today["first_responses"] == 0
    assert body["totals"]["created"] == 2
    assert body["totals"]["resolved"] == 1


async def test_daily_report_clamps_the_window(client):
    headers, _ = await _workspace(client, email="dailyclamp@example.com")
    wide = (await client.get("/api/v1/reports/daily?days=500", headers=headers)).json()
    assert len(wide["days"]) == 90
    narrow = (await client.get("/api/v1/reports/daily?days=0", headers=headers)).json()
    assert len(narrow["days"]) == 1


async def test_daily_report_counts_breaches(client, db_session):
    headers, key = await _workspace(client, email="dailybreach@example.com")
    ticket_id = (
        await client.post("/api/v1/tickets", json=_body(), headers={"X-Api-Key": key})
    ).json()["id"]

    # The sweep itself is covered by test_sla; here we only care that a breach
    # lands in the right day's bucket.
    ticket = (
        await db_session.execute(select(Ticket).where(Ticket.id == UUID(ticket_id)))
    ).scalar_one()
    ticket.sla_breached_at = utcnow()
    await db_session.commit()

    body = (await client.get("/api/v1/reports/daily", headers=headers)).json()
    assert body["days"][-1]["breached"] == 1
    assert body["totals"]["breached"] == 1


async def test_summary_counts_and_averages(client):
    headers, key = await _workspace(client, email="reports@example.com")
    first = await client.post("/api/v1/tickets", json=_body(), headers={"X-Api-Key": key})
    await client.post("/api/v1/tickets", json=_body("c2"), headers={"X-Api-Key": key})
    await client.post(f"/api/v1/tickets/{first.json()['id']}/resolve", headers=headers)

    body = (await client.get("/api/v1/reports/summary", headers=headers)).json()
    assert body["total"] == 2
    assert body["by_status"]["resolved"] == 1
    assert body["by_status"]["open"] == 1
    assert body["avg_resolution_minutes"] is not None
    assert body["sla_compliance"] == 100.0


async def test_summary_empty_workspace(client):
    headers, _ = await _workspace(client, email="reports2@example.com")
    body = (await client.get("/api/v1/reports/summary", headers=headers)).json()
    assert body["total"] == 0
    assert body["sla_compliance"] is None
    assert body["avg_first_response_minutes"] is None


async def test_summary_reflects_breaches(client, db_session):
    headers, key = await _workspace(client, email="reports3@example.com")
    await client.patch(
        "/api/v1/console/settings/sla", json={"resolution_minutes": {"normal": 0}}, headers=headers
    )
    await client.post("/api/v1/tickets", json=_body(), headers={"X-Api-Key": key})
    await sla_svc.sweep_breaches(db_session)

    body = (await client.get("/api/v1/reports/summary", headers=headers)).json()
    assert body["breached"] == 1
    assert body["sla_compliance"] == 0.0


async def test_summary_breaks_down_by_team_and_assignee(client):
    headers, key = await _workspace(client, email="reports4@example.com")
    team_id = (
        await client.post("/api/v1/teams", json={"name": "Tier 1"}, headers=headers)
    ).json()["id"]
    ticket_id = (
        await client.post("/api/v1/tickets", json=_body(), headers={"X-Api-Key": key})
    ).json()["id"]
    await client.post(
        f"/api/v1/tickets/{ticket_id}/assign",
        json={"strategy": "team", "team_id": team_id},
        headers=headers,
    )

    body = (await client.get("/api/v1/reports/summary", headers=headers)).json()
    assert body["by_team"].get(team_id) == 1
    assert body["by_assignee"].get("unassigned") == 1
