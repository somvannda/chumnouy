"""AI assistant: grounding, streaming, conversations, feedback and drafting.

Provider calls are stubbed (``stream_chat`` / ``complete_chat``) and the
post-stream persistence is redirected onto the test session, so no network or
real database is touched.
"""
import uuid

import pytest
from sqlalchemy import select

from app.models import AssistantConversation, Workspace
from app.services import ai as ai_service
from app.services import assistant as svc

pytestmark = pytest.mark.asyncio


async def _signup(client, *, email, workspace="Acme Support"):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
    )
    assert signup.status_code == 201, signup.text
    token = signup.json()["token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _configure_ai(db_session):
    workspace = (await db_session.execute(select(Workspace))).scalars().first()
    workspace.settings = {**(workspace.settings or {}), "ai_provider": "openai", "ai_api_key": "sk-test"}
    await db_session.commit()
    return workspace


def _stub_provider(monkeypatch, *, chunks=("Refunds ", "take 3 days."), draft="Thanks, we will follow up."):
    async def fake_stream(workspace, *, system, messages, temperature=0.3, max_tokens=900, usage_out=None):
        if usage_out is not None:
            usage_out.update({"provider": "openai", "model": "gpt-4o-mini"})
        for chunk in chunks:
            yield chunk

    async def fake_complete(workspace, *, system, messages, temperature=0.3, max_tokens=900):
        return {"content": draft, "provider": "openai", "model": "gpt-4o-mini", "usage": {}}

    monkeypatch.setattr(ai_service, "stream_chat", fake_stream)
    monkeypatch.setattr(ai_service, "complete_chat", fake_complete)


async def _patch_persistence(monkeypatch, db_session):
    async def fake_persist(*, conversation_id, role, content, citations=None, usage=None):
        conversation = await db_session.get(AssistantConversation, conversation_id)
        message = await svc.add_message(
            db_session, conversation, role=role, content=content, citations=citations, usage=usage
        )
        await db_session.commit()
        return message.id

    monkeypatch.setattr(svc, "persist_message_standalone", fake_persist)


async def test_chat_requires_configuration(client):
    _, headers = await _signup(client, email="unset@example.com")
    resp = await client.post("/api/v1/assistant/chat", json={"question": "How do refunds work?"}, headers=headers)
    assert resp.status_code == 400
    assert "configured" in resp.json()["error"]["message"].lower()


async def test_chat_streams_a_grounded_answer(client, db_session, monkeypatch):
    _, headers = await _signup(client, email="chat@example.com")
    await _configure_ai(db_session)
    _stub_provider(monkeypatch)
    await _patch_persistence(monkeypatch, db_session)

    resp = await client.post(
        "/api/v1/assistant/chat", json={"question": "How do refunds work?"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "event: citation" in resp.text
    assert "event: token" in resp.text
    assert "Refunds " in resp.text
    assert "event: done" in resp.text

    conversations = await client.get("/api/v1/assistant/conversations", headers=headers)
    assert conversations.status_code == 200
    assert len(conversations.json()) == 1
    conversation_id = conversations.json()[0]["id"]

    detail = await client.get(f"/api/v1/assistant/conversations/{conversation_id}", headers=headers)
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "Refunds take 3 days."
    assert messages[1]["citations"], "answer should cite the workspace corpus"


async def test_feedback_records_and_validates_message(client, db_session, monkeypatch):
    _, headers = await _signup(client, email="feedback@example.com")
    await _configure_ai(db_session)
    _stub_provider(monkeypatch)
    await _patch_persistence(monkeypatch, db_session)
    await client.post("/api/v1/assistant/chat", json={"question": "How do refunds work?"}, headers=headers)

    conversation_id = (await client.get("/api/v1/assistant/conversations", headers=headers)).json()[0]["id"]
    detail = (await client.get(f"/api/v1/assistant/conversations/{conversation_id}", headers=headers)).json()
    answer_id = detail["messages"][1]["id"]

    rated = await client.post(
        "/api/v1/assistant/feedback",
        json={"message_id": answer_id, "rating": "up", "comment": "spot on"},
        headers=headers,
    )
    assert rated.status_code == 201, rated.text
    assert rated.json()["rating"] == "up"

    missing = await client.post(
        "/api/v1/assistant/feedback",
        json={"message_id": str(uuid.uuid4()), "rating": "down"},
        headers=headers,
    )
    assert missing.status_code == 404


async def test_ticket_draft(client, db_session, monkeypatch):
    token, headers = await _signup(client, email="draft@example.com")
    await _configure_ai(db_session)
    _stub_provider(monkeypatch, draft="We have reissued your receipt.")

    integration = await client.post(
        "/api/v1/integrations", json={"name": "POS", "scopes": ["tickets:read", "tickets:write"]}, headers=headers
    )
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]
    ticket = await client.post(
        "/api/v1/tickets",
        json={"subject": "Missing receipt", "message": "I need my receipt.", "requester": {"external_id": "c1"}},
        headers={"X-Api-Key": key},
    )
    ticket_id = ticket.json()["id"]

    drafted = await client.post(
        f"/api/v1/tickets/{ticket_id}/assistant/draft",
        json={"instruction": "be brief"},
        headers=headers,
    )
    assert drafted.status_code == 200, drafted.text
    assert drafted.json()["draft"] == "We have reissued your receipt."

    missing = await client.post(
        f"/api/v1/tickets/{uuid.uuid4()}/assistant/draft", json={}, headers=headers
    )
    assert missing.status_code == 404


async def test_conversations_are_workspace_scoped(client, db_session, monkeypatch):
    _, headers_a = await _signup(client, email="a@example.com", workspace="Workspace A")
    _, headers_b = await _signup(client, email="b@example.com", workspace="Workspace B")
    await _configure_ai(db_session)
    _stub_provider(monkeypatch)
    await _patch_persistence(monkeypatch, db_session)

    await client.post("/api/v1/assistant/chat", json={"question": "How do refunds work?"}, headers=headers_a)
    conversation_id = (await client.get("/api/v1/assistant/conversations", headers=headers_a)).json()[0]["id"]

    assert (await client.get("/api/v1/assistant/conversations", headers=headers_b)).json() == []
    denied = await client.get(f"/api/v1/assistant/conversations/{conversation_id}", headers=headers_b)
    assert denied.status_code == 404


async def test_chat_requires_use_scope(client):
    token, _ = await _signup(client, email="scope@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    integration = await client.post(
        "/api/v1/integrations", json={"name": "Reader", "scopes": ["tickets:read"]}, headers=headers
    )
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]

    denied = await client.post(
        "/api/v1/assistant/chat", json={"question": "How do refunds work?"}, headers={"X-Api-Key": key}
    )
    assert denied.status_code == 403
