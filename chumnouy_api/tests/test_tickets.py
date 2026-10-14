import pytest

pytestmark = pytest.mark.asyncio


async def _workspace_with_key(client, *, email: str, name: str = "Owner", workspace: str = "Acme Support"):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": name, "workspace_name": workspace},
    )
    assert signup.status_code == 201, signup.text
    token = signup.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    integration = await client.post(
        "/api/v1/integrations",
        json={"name": "Chmaba POS", "scopes": ["tickets:read", "tickets:write"]},
        headers=headers,
    )
    assert integration.status_code == 201, integration.text
    integration_id = integration.json()["id"]
    key_resp = await client.post(
        f"/api/v1/integrations/{integration_id}/keys",
        json={"name": "k", "environment": "live"},
        headers=headers,
    )
    assert key_resp.status_code == 201, key_resp.text
    return token, key_resp.json()["key"]


def _ticket_body(subject: str = "Card reader not charging") -> dict:
    return {
        "subject": subject,
        "message": "The terminal stopped charging this morning.",
        "requester": {
            "external_id": "cust_88213",
            "name": "Sok Dara",
            "email": "dara@example.com",
        },
        "priority": "high",
        "tags": ["hardware"],
        "metadata": {"store_id": "store_7"},
    }


async def test_create_ticket_via_api_key(client):
    _, key = await _workspace_with_key(client, email="a@example.com")
    resp = await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["reference"].startswith("CMY-")
    assert body["status"] == "open"
    assert body["priority"] == "high"
    assert body["requester"]["external_id"] == "cust_88213"
    assert body["metadata"] == {"store_id": "store_7"}
    assert len(body["messages"]) == 1
    assert body["messages"][0]["author_type"] == "requester"

    detail = await client.get(f"/api/v1/tickets/{body['id']}", headers={"X-Api-Key": key})
    assert detail.status_code == 200
    assert detail.json()["messages"][0]["body"].startswith("The terminal")


async def test_agent_reply_and_resolve_via_jwt(client):
    token, key = await _workspace_with_key(client, email="b@example.com")
    created = await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})
    ticket_id = created.json()["id"]
    headers = {"Authorization": f"Bearer {token}"}

    reply = await client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        json={"body": "Please reseat the cable.", "visibility": "public"},
        headers=headers,
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["author_type"] == "agent"

    resolved = await client.post(f"/api/v1/tickets/{ticket_id}/resolve", headers=headers)
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_at"] is not None

    listing = await client.get("/api/v1/tickets?status=resolved", headers=headers)
    assert listing.status_code == 200
    assert [t["id"] for t in listing.json()["data"]] == [ticket_id]

    events = await client.get(f"/api/v1/tickets/{ticket_id}/events", headers=headers)
    assert events.status_code == 200
    types = [e["type"] for e in events.json()]
    assert "ticket.created" in types
    assert "ticket.resolved" in types


async def test_read_only_key_cannot_create(client):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": "c@example.com", "password": "supersecret123", "name": "Owner"},
    )
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}
    integration = await client.post(
        "/api/v1/integrations", json={"name": "Reader", "scopes": ["tickets:read"]}, headers=headers
    )
    key_resp = await client.post(
        f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
    )
    key = key_resp.json()["key"]

    denied = await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})
    assert denied.status_code == 403

    allowed = await client.get("/api/v1/tickets", headers={"X-Api-Key": key})
    assert allowed.status_code == 200


async def test_tickets_are_workspace_isolated(client):
    _, key_a = await _workspace_with_key(client, email="a@example.com", workspace="Workspace A")
    _, key_b = await _workspace_with_key(client, email="b@example.com", workspace="Workspace B")

    created = await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key_a})
    ticket_id = created.json()["id"]

    listing_b = await client.get("/api/v1/tickets", headers={"X-Api-Key": key_b})
    assert listing_b.status_code == 200
    assert listing_b.json()["data"] == []

    fetch_b = await client.get(f"/api/v1/tickets/{ticket_id}", headers={"X-Api-Key": key_b})
    assert fetch_b.status_code == 404


async def test_tickets_require_auth(client):
    resp = await client.get("/api/v1/tickets")
    assert resp.status_code == 401
