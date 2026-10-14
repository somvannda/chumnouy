"""Requesters and the public (requester-token) surface.

Portal tokens scope an external end user to their own workspace and tickets; the
public read only ever returns public messages, hiding internal notes.
"""
import pytest

pytestmark = pytest.mark.asyncio


async def _signup(client, *, email, workspace="Acme Support"):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
    )
    assert signup.status_code == 201, signup.text
    token = signup.json()["token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _key(client, headers, *, scopes):
    integration = await client.post(
        "/api/v1/integrations", json={"name": "POS", "scopes": scopes}, headers=headers
    )
    return (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]


def _ticket_body(external_id="cust_1", subject="Card reader down"):
    return {
        "subject": subject,
        "message": "The terminal stopped charging.",
        "requester": {"external_id": external_id, "name": "Sok Dara", "email": "dara@example.com"},
    }


async def _requester_with_token(client, headers, key):
    await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})
    requester = (await client.get("/api/v1/requesters", headers=headers)).json()[0]
    issued = await client.post(
        f"/api/v1/requesters/{requester['id']}/portal-token", headers=headers
    )
    assert issued.status_code == 201, issued.text
    return requester, issued.json()["token"]


async def test_requesters_list_detail_and_update(client):
    token, headers = await _signup(client, email="req@example.com")
    key = await _key(client, headers, scopes=["tickets:read", "tickets:write", "requesters:read", "requesters:write"])
    await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})

    listing = await client.get("/api/v1/requesters?q=dara", headers=headers)
    assert listing.status_code == 200, listing.text
    requester = listing.json()[0]
    assert requester["external_id"] == "cust_1"
    assert "portal_token_hash" not in requester

    detail = await client.get(f"/api/v1/requesters/{requester['id']}", headers=headers)
    assert detail.status_code == 200
    assert [t["reference"] for t in detail.json()["tickets"]][0].startswith("CMY-")

    updated = await client.patch(
        f"/api/v1/requesters/{requester['id']}",
        json={"phone": "+85510000000", "metadata": {"tier": "gold"}},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["phone"] == "+85510000000"
    assert updated.json()["metadata"]["tier"] == "gold"


async def test_portal_flow_creates_lists_and_replies(client):
    _, headers = await _signup(client, email="portal@example.com")
    key = await _key(client, headers, scopes=["tickets:read", "tickets:write", "requesters:write"])
    _, token = await _requester_with_token(client, headers, key)
    portal = {"X-Requester-Token": token}

    created = await client.post(
        "/api/v1/public/tickets",
        json={"subject": "Refund please", "message": "I want a refund."},
        headers=portal,
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["id"]

    mine = await client.get("/api/v1/public/tickets", headers=portal)
    assert mine.status_code == 200
    assert ticket_id in [t["id"] for t in mine.json()["data"]]

    reply = await client.post(
        f"/api/v1/public/tickets/{ticket_id}/messages",
        json={"body": "Any update?"},
        headers=portal,
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["author_type"] == "requester"


async def test_internal_notes_are_hidden_from_the_requester(client):
    _, headers = await _signup(client, email="hidden@example.com")
    key = await _key(client, headers, scopes=["tickets:read", "tickets:write", "requesters:write"])
    created = await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})
    ticket_id = created.json()["id"]
    await client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        json={"body": "Internal: refund already issued.", "visibility": "internal"},
        headers=headers,
    )

    requester = (await client.get("/api/v1/requesters", headers=headers)).json()[0]
    token = (
        await client.post(f"/api/v1/requesters/{requester['id']}/portal-token", headers=headers)
    ).json()["token"]

    detail = await client.get(f"/api/v1/public/tickets/{ticket_id}", headers={"X-Requester-Token": token})
    assert detail.status_code == 200
    bodies = [m["body"] for m in detail.json()["messages"]]
    assert "Internal: refund already issued." not in bodies
    assert len(bodies) == 1


async def test_portal_token_is_required_and_scoped(client):
    _, headers = await _signup(client, email="scope2@example.com")
    key = await _key(client, headers, scopes=["tickets:read", "tickets:write", "requesters:write"])
    _, token_a = await _requester_with_token(client, headers, key)

    assert (await client.get("/api/v1/public/tickets")).status_code == 401
    assert (
        await client.get("/api/v1/public/tickets", headers={"X-Requester-Token": "rqt_bogus"})
    ).status_code == 401

    other = await client.post(
        "/api/v1/public/tickets",
        json={"subject": "Other", "message": "hi"},
        headers={"X-Requester-Token": token_a},
    )
    other_id = other.json()["id"]

    # A second requester (with their own token) cannot read the first's ticket.
    await client.post("/api/v1/tickets", json=_ticket_body(external_id="cust_2"), headers={"X-Api-Key": key})
    requester_b = (await client.get("/api/v1/requesters?q=cust_2", headers=headers)).json()[0]
    token_b = (
        await client.post(f"/api/v1/requesters/{requester_b['id']}/portal-token", headers=headers)
    ).json()["token"]

    denied = await client.get(
        f"/api/v1/public/tickets/{other_id}", headers={"X-Requester-Token": token_b}
    )
    assert denied.status_code == 404


async def test_requesters_require_scope(client):
    _, headers = await _signup(client, email="scopereq@example.com")
    key = await _key(client, headers, scopes=["tickets:read"])

    denied = await client.get("/api/v1/requesters", headers={"X-Api-Key": key})
    assert denied.status_code == 403

    allowed = await client.get("/api/v1/requesters", headers=headers)
    assert allowed.status_code == 200
