"""Workspace settings: AI provider + Notifyr config, secrets write-only, roles."""
import pytest
from sqlalchemy import select

from app.models import AssistantConversation, Membership, User
from app.services import ai as ai_service
from app.services import assistant as assistant_svc

pytestmark = pytest.mark.asyncio


async def _signup(client, *, email, workspace="Acme Support"):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
    )
    assert signup.status_code == 201, signup.text
    token = signup.json()["token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _set_role(db_session, email, role):
    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    membership = (
        await db_session.execute(select(Membership).where(Membership.user_id == user.id))
    ).scalar_one()
    membership.role = role
    await db_session.commit()


async def test_settings_defaults_are_unconfigured(client):
    _, headers = await _signup(client, email="defaults@example.com")
    resp = await client.get("/api/v1/console/settings", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ai"]["api_key_set"] is False
    assert body["ai"]["provider"] is None
    assert {p["code"] for p in body["ai"]["providers"]} == {"openai", "deepseek", "anthropic"}
    assert body["notifications"] == {"notifyr_api_url": None, "notifyr_api_key_set": False}


async def test_ai_settings_unblock_the_assistant(client, db_session, monkeypatch):
    _, headers = await _signup(client, email="aiconf@example.com")

    # Unconfigured: the assistant refuses.
    assert (await client.post("/api/v1/assistant/chat", json={"question": "hi"}, headers=headers)).status_code == 400

    patched = await client.patch(
        "/api/v1/console/settings/ai",
        json={"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-test"},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["provider"] == "openai"
    assert patched.json()["api_key_set"] is True

    async def fake_stream(workspace, *, system, messages, temperature=0.3, max_tokens=900, usage_out=None):
        yield "ok"

    async def fake_persist(*, conversation_id, role, content, citations=None, usage=None):
        conversation = await db_session.get(AssistantConversation, conversation_id)
        message = await assistant_svc.add_message(
            db_session, conversation, role=role, content=content, citations=citations, usage=usage
        )
        await db_session.commit()
        return message.id

    monkeypatch.setattr(ai_service, "stream_chat", fake_stream)
    monkeypatch.setattr(assistant_svc, "persist_message_standalone", fake_persist)

    chat = await client.post("/api/v1/assistant/chat", json={"question": "hi"}, headers=headers)
    assert chat.status_code == 200, chat.text

    # An empty api_key clears the override.
    cleared = await client.patch("/api/v1/console/settings/ai", json={"api_key": ""}, headers=headers)
    assert cleared.json()["api_key_set"] is False


async def test_notification_settings(client):
    _, headers = await _signup(client, email="notify@example.com")
    patched = await client.patch(
        "/api/v1/console/settings/notifications",
        json={"notifyr_api_url": "https://notifyr.example.com", "notifyr_api_key": "nkey"},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["notifyr_api_url"] == "https://notifyr.example.com"
    assert patched.json()["notifyr_api_key_set"] is True

    read = await client.get("/api/v1/console/settings", headers=headers)
    assert read.json()["notifications"]["notifyr_api_url"] == "https://notifyr.example.com"


async def test_settings_require_owner_or_admin(client, db_session):
    _, headers = await _signup(client, email="agent-role@example.com")
    await _set_role(db_session, "agent-role@example.com", "agent")

    assert (await client.get("/api/v1/console/settings", headers=headers)).status_code == 403
    denied = await client.patch(
        "/api/v1/console/settings/ai", json={"provider": "openai"}, headers=headers
    )
    assert denied.status_code == 403
