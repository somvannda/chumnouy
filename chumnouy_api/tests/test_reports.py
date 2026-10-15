"""Reports: workspace summary counts, averages and SLA compliance."""
import pytest

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
