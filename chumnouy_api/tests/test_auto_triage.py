"""Auto-apply triage: when enabled, a new ticket gets the assistant's suggestion."""
import pytest

from app.services import assistant as assistant_svc

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


def _ticket():
    return {"subject": "Terminal down", "message": "It will not charge.", "requester": {"external_id": "c1"}}


async def test_auto_triage_applies_the_suggestion(client, monkeypatch):
    headers, key = await _workspace(client, email="autotriage@example.com")
    await client.patch(
        "/api/v1/console/settings/ai",
        json={"provider": "openai", "api_key": "sk-test", "auto_triage": True},
        headers=headers,
    )

    async def fake_triage(workspace, *, ticket, messages):
        return {"priority": "high", "tags": ["hardware"], "provider": "openai", "model": "m"}

    monkeypatch.setattr(assistant_svc, "suggest_triage", fake_triage)

    created = await client.post("/api/v1/tickets", json=_ticket(), headers={"X-Api-Key": key})
    assert created.status_code == 201, created.text
    assert created.json()["priority"] == "high"
    assert "hardware" in created.json()["tags"]


async def test_auto_triage_off_by_default(client, monkeypatch):
    _, key = await _workspace(client, email="autotriage2@example.com")
    called = {"n": 0}

    async def fake_triage(workspace, *, ticket, messages):
        called["n"] += 1
        return {"priority": "high", "tags": []}

    monkeypatch.setattr(assistant_svc, "suggest_triage", fake_triage)

    created = await client.post("/api/v1/tickets", json=_ticket(), headers={"X-Api-Key": key})
    assert created.json()["priority"] == "normal"
    assert called["n"] == 0
