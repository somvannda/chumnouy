"""CSAT: rating a ticket via the requester portal, and it appearing in reports."""
import pytest

pytestmark = pytest.mark.asyncio


def _body(external_id="c1"):
    return {"subject": "Hi", "message": "hello", "requester": {"external_id": external_id}}


async def _setup(client, email):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": "Acme"},
    )
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}
    integration = await client.post(
        "/api/v1/integrations",
        json={"name": "POS", "scopes": ["tickets:read", "tickets:write", "requesters:write"]},
        headers=headers,
    )
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]
    created = await client.post("/api/v1/tickets", json=_body(), headers={"X-Api-Key": key})
    ticket_id = created.json()["id"]
    requester = (await client.get("/api/v1/requesters?q=c1", headers=headers)).json()[0]
    token = (
        await client.post(f"/api/v1/requesters/{requester['id']}/portal-token", headers=headers)
    ).json()["token"]
    return headers, key, ticket_id, token


async def test_submit_csat_and_see_it_in_reports(client):
    headers, _, ticket_id, token = await _setup(client, "csat@example.com")
    portal = {"X-Requester-Token": token}

    submitted = await client.post(
        f"/api/v1/public/tickets/{ticket_id}/csat",
        json={"rating": "up", "comment": "Great support"},
        headers=portal,
    )
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["rating"] == "up"

    summary = (await client.get("/api/v1/reports/summary", headers=headers)).json()
    assert summary["csat_responses"] == 1
    assert summary["csat_positive_pct"] == 100.0

    # Re-rating updates the single response.
    await client.post(
        f"/api/v1/public/tickets/{ticket_id}/csat", json={"rating": "down"}, headers=portal
    )
    summary = (await client.get("/api/v1/reports/summary", headers=headers)).json()
    assert summary["csat_responses"] == 1
    assert summary["csat_positive_pct"] == 0.0


async def test_csat_is_scoped_to_the_requester(client):
    headers, key, ticket_id, _ = await _setup(client, "csat2@example.com")
    await client.post("/api/v1/tickets", json=_body("c2"), headers={"X-Api-Key": key})
    other = (await client.get("/api/v1/requesters?q=c2", headers=headers)).json()[0]
    other_token = (
        await client.post(f"/api/v1/requesters/{other['id']}/portal-token", headers=headers)
    ).json()["token"]

    denied = await client.post(
        f"/api/v1/public/tickets/{ticket_id}/csat",
        json={"rating": "up"},
        headers={"X-Requester-Token": other_token},
    )
    assert denied.status_code == 404
