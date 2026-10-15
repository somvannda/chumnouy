"""AI depth: thread summarisation and ticket triage."""
import pytest

from app.services import ai as ai_service

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


async def _ticket(client, key):
    resp = await client.post(
        "/api/v1/tickets",
        json={
            "subject": "Terminal down",
            "message": "The terminal will not charge.",
            "requester": {"external_id": "c1"},
        },
        headers={"X-Api-Key": key},
    )
    return resp.json()["id"]


async def test_summary_and_triage(client, monkeypatch):
    headers, key = await _workspace(client, email="ai@example.com")
    await client.patch(
        "/api/v1/console/settings/ai",
        json={"provider": "openai", "api_key": "sk-test"},
        headers=headers,
    )
    ticket_id = await _ticket(client, key)

    calls = {"n": 0}

    async def fake_complete(workspace, *, system, messages, temperature=0.3, max_tokens=900):
        calls["n"] += 1
        if "triage" in system.lower():
            content = '{"priority": "high", "tags": ["hardware", "terminal"]}'
        else:
            content = "Customer reports a terminal that will not charge; unresolved."
        return {"content": content, "provider": "openai", "model": "gpt-4o-mini", "usage": {}}

    monkeypatch.setattr(ai_service, "complete_chat", fake_complete)

    summary = await client.post(f"/api/v1/tickets/{ticket_id}/assistant/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    assert "terminal" in summary.json()["summary"].lower()
    assert summary.json()["provider"] == "openai"

    triage = await client.post(f"/api/v1/tickets/{ticket_id}/assistant/triage", headers=headers)
    assert triage.status_code == 200, triage.text
    assert triage.json()["priority"] == "high"
    assert triage.json()["tags"] == ["hardware", "terminal"]
    assert calls["n"] == 2


async def test_triage_falls_back_on_bad_json(client, monkeypatch):
    headers, key = await _workspace(client, email="ai2@example.com")
    await client.patch(
        "/api/v1/console/settings/ai",
        json={"provider": "openai", "api_key": "sk-test"},
        headers=headers,
    )
    ticket_id = await _ticket(client, key)

    async def fake_complete(workspace, *, system, messages, temperature=0.3, max_tokens=900):
        return {"content": "not json at all", "provider": "openai", "model": "m", "usage": {}}

    monkeypatch.setattr(ai_service, "complete_chat", fake_complete)
    triage = await client.post(f"/api/v1/tickets/{ticket_id}/assistant/triage", headers=headers)
    assert triage.status_code == 200
    assert triage.json()["priority"] == "normal"  # the ticket's own priority
    assert triage.json()["tags"] == []


async def test_summary_requires_configuration(client):
    headers, key = await _workspace(client, email="ai3@example.com")
    ticket_id = await _ticket(client, key)
    resp = await client.post(f"/api/v1/tickets/{ticket_id}/assistant/summary", headers=headers)
    assert resp.status_code == 400
    assert "configured" in resp.json()["error"]["message"].lower()


async def test_triage_requires_use_scope(client):
    _, key = await _workspace(client, email="ai4@example.com")
    resp = await client.post(
        "/api/v1/tickets/11111111-1111-1111-1111-111111111111/assistant/triage",
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 403
