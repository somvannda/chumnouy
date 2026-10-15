"""GDPR: requester data export and erasure."""
import pytest

pytestmark = pytest.mark.asyncio


async def _workspace(
    client,
    *,
    email,
    workspace="Acme Support",
    scopes=("tickets:read", "tickets:write", "requesters:read", "requesters:write"),
):
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


async def _requester_with_ticket(client, headers, key):
    await client.post(
        "/api/v1/tickets",
        json={
            "subject": "Data subject",
            "message": "please export me",
            "requester": {"external_id": "ds1", "name": "Dara", "email": "dara@example.com"},
        },
        headers={"X-Api-Key": key},
    )
    return (await client.get("/api/v1/requesters?q=ds1", headers=headers)).json()[0]


async def test_export_includes_profile_tickets_and_messages(client):
    headers, key = await _workspace(client, email="gdpr@example.com")
    requester = await _requester_with_ticket(client, headers, key)

    resp = await client.get(f"/api/v1/requesters/{requester['id']}/export", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["requester"]["external_id"] == "ds1"
    assert len(body["tickets"]) == 1
    assert body["tickets"][0]["messages"][0]["body"] == "please export me"


async def test_erasure_removes_the_requester_and_their_tickets(client):
    headers, key = await _workspace(client, email="gdpr2@example.com")
    requester = await _requester_with_ticket(client, headers, key)
    ticket_id = (await client.get("/api/v1/tickets", headers=headers)).json()["data"][0]["id"]

    deleted = await client.delete(f"/api/v1/requesters/{requester['id']}", headers=headers)
    assert deleted.status_code == 204

    assert (await client.get(f"/api/v1/requesters/{requester['id']}", headers=headers)).status_code == 404
    assert (await client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)).status_code == 404
    assert (await client.get("/api/v1/tickets", headers=headers)).json()["data"] == []


async def test_export_requires_scope_and_is_isolated(client):
    headers_a, key_a = await _workspace(client, email="a@example.com", workspace="Workspace A")
    headers_b, _ = await _workspace(client, email="b@example.com", workspace="Workspace B")
    requester = await _requester_with_ticket(client, headers_a, key_a)

    assert (
        await client.get(f"/api/v1/requesters/{requester['id']}/export", headers=headers_b)
    ).status_code == 404

    _, read_key = await _workspace(client, email="c@example.com", scopes=("requesters:read",))
    denied = await client.delete(
        f"/api/v1/requesters/{requester['id']}", headers={"X-Api-Key": read_key}
    )
    assert denied.status_code == 403
