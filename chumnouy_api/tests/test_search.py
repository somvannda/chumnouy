"""Search across tickets, messages and articles; workspace-scoped."""
import pytest

pytestmark = pytest.mark.asyncio


async def _workspace(client, *, email, workspace="Acme Support"):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
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


async def test_search_matches_subject_body_and_articles(client):
    headers, key = await _workspace(client, email="search@example.com")
    created = await client.post(
        "/api/v1/tickets",
        json={
            "subject": "Card reader not charging",
            "message": "The terminal stopped charging this morning.",
            "requester": {"external_id": "c1"},
        },
        headers={"X-Api-Key": key},
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["id"]
    await client.post(
        "/api/v1/knowledge/articles",
        json={"title": "Charging basics", "body": "Reseat the charging cable."},
        headers=headers,
    )

    subject_hit = await client.get("/api/v1/search?q=charging", headers=headers)
    assert subject_hit.status_code == 200, subject_hit.text
    types = {r["type"] for r in subject_hit.json()["results"]}
    assert "ticket" in types and "article" in types

    message_hit = await client.get("/api/v1/search?q=terminal", headers=headers)
    results = message_hit.json()["results"]
    assert results and results[0]["type"] == "message"
    assert results[0]["ticket_id"] == ticket_id
    assert results[0]["reference"].startswith("CMY-")
    assert "terminal" in results[0]["snippet"].lower()


async def test_search_type_filter_and_limit(client):
    headers, key = await _workspace(client, email="search2@example.com")
    await client.post(
        "/api/v1/tickets",
        json={"subject": "Refund please", "message": "refund refund", "requester": {"external_id": "c1"}},
        headers={"X-Api-Key": key},
    )
    only_tickets = await client.get("/api/v1/search?q=refund&types=ticket", headers=headers)
    assert {r["type"] for r in only_tickets.json()["results"]} == {"ticket"}
    limited = await client.get("/api/v1/search?q=refund&limit=1", headers=headers)
    assert len(limited.json()["results"]) == 1


async def test_search_is_workspace_isolated(client):
    _, key_a = await _workspace(client, email="a@example.com", workspace="Workspace A")
    headers_b, _ = await _workspace(client, email="b@example.com", workspace="Workspace B")
    await client.post(
        "/api/v1/tickets",
        json={"subject": "Unique AAAA", "message": "secret", "requester": {"external_id": "c1"}},
        headers={"X-Api-Key": key_a},
    )
    results = await client.get("/api/v1/search?q=AAAA", headers=headers_b)
    assert results.status_code == 200
    assert results.json()["results"] == []
