"""Idempotent writes: a repeated Idempotency-Key returns the original response."""
import pytest

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


def _body():
    return {"subject": "Hi", "message": "hello", "requester": {"external_id": "c1"}}


async def test_same_key_returns_the_same_ticket(client):
    headers, key = await _workspace(client, email="idem@example.com")
    request_headers = {"X-Api-Key": key, "Idempotency-Key": "req-1"}

    first = await client.post("/api/v1/tickets", json=_body(), headers=request_headers)
    second = await client.post("/api/v1/tickets", json=_body(), headers=request_headers)

    assert first.status_code == 201, first.text
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len((await client.get("/api/v1/tickets", headers=headers)).json()["data"]) == 1


async def test_different_keys_create_different_tickets(client):
    headers, key = await _workspace(client, email="idem2@example.com")

    first = await client.post(
        "/api/v1/tickets", json=_body(), headers={"X-Api-Key": key, "Idempotency-Key": "a"}
    )
    second = await client.post(
        "/api/v1/tickets", json=_body(), headers={"X-Api-Key": key, "Idempotency-Key": "b"}
    )

    assert first.json()["id"] != second.json()["id"]
    assert len((await client.get("/api/v1/tickets", headers=headers)).json()["data"]) == 2


async def test_without_a_key_every_call_creates_a_ticket(client):
    headers, key = await _workspace(client, email="idem3@example.com")

    first = await client.post("/api/v1/tickets", json=_body(), headers={"X-Api-Key": key})
    second = await client.post("/api/v1/tickets", json=_body(), headers={"X-Api-Key": key})

    assert first.json()["id"] != second.json()["id"]


async def test_reply_is_idempotent(client):
    headers, key = await _workspace(client, email="idem4@example.com")
    ticket_id = (
        await client.post("/api/v1/tickets", json=_body(), headers={"X-Api-Key": key})
    ).json()["id"]

    request_headers = {**headers, "Idempotency-Key": "reply-1"}
    first = await client.post(
        f"/api/v1/tickets/{ticket_id}/messages", json={"body": "on it"}, headers=request_headers
    )
    second = await client.post(
        f"/api/v1/tickets/{ticket_id}/messages", json={"body": "on it"}, headers=request_headers
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    # The opening message plus exactly one reply.
    detail = await client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert len(detail.json()["messages"]) == 2
