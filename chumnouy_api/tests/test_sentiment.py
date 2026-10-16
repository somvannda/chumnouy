"""Sentiment scoring: AI-labelled requester messages, scored in the worker."""
import pytest
from sqlalchemy import select

from app.models import Workspace
from app.services import ai as ai_service
from app.services import sentiment as sentiment_svc

pytestmark = pytest.mark.asyncio


async def _workspace(client, *, email, ai=True):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": "Acme"},
    )
    assert signup.status_code == 201, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}
    if ai:
        await client.patch(
            "/api/v1/console/settings/ai",
            json={"provider": "openai", "api_key": "sk-test"},
            headers=headers,
        )
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


async def _ticket(client, key, *, message="This is broken and I am furious"):
    created = await client.post(
        "/api/v1/tickets",
        json={"subject": "Help", "message": message, "requester": {"external_id": "s1"}},
        headers={"X-Api-Key": key},
    )
    assert created.status_code == 201, created.text
    return created.json()


def _fake_reply(label):
    """Mirror ``ai_service.complete_chat``, which returns a dict, not a string."""

    async def fake_complete(workspace, *, system, messages, temperature=0.3, max_tokens=900):
        assert "classify" in system.lower()
        assert messages[-1]["content"]
        return {"content": label, "provider": "openai", "model": "gpt-4o-mini", "usage": {}}

    return fake_complete


async def test_ticket_sentiment_is_scored_by_the_worker(client, db_session, monkeypatch):
    headers, key = await _workspace(client, email="sentiment@example.com")
    ticket = await _ticket(client, key)
    assert ticket["sentiment"] is None

    monkeypatch.setattr(ai_service, "complete_chat", _fake_reply("negative"))
    assert await sentiment_svc.score_pending(db_session) == 1

    detail = (await client.get(f"/api/v1/tickets/{ticket['id']}", headers=headers)).json()
    assert detail["sentiment"] == "negative"

    # Already scored: the next sweep has nothing to do.
    assert await sentiment_svc.score_pending(db_session) == 0

    summary = (await client.get("/api/v1/reports/summary", headers=headers)).json()
    assert summary["by_sentiment"] == {"negative": 1}


async def test_scoring_is_skipped_without_ai(client, db_session, monkeypatch):
    _, key = await _workspace(client, email="sentimentnoai@example.com", ai=False)
    await _ticket(client, key)

    monkeypatch.setattr(ai_service, "complete_chat", _fake_reply("positive"))
    assert await sentiment_svc.score_pending(db_session) == 0


async def test_unparseable_replies_are_left_unscored(client, db_session, monkeypatch):
    headers, key = await _workspace(client, email="sentimentbad@example.com")
    ticket = await _ticket(client, key)

    monkeypatch.setattr(ai_service, "complete_chat", _fake_reply("I cannot help with that"))
    assert await sentiment_svc.score_pending(db_session) == 0

    detail = (await client.get(f"/api/v1/tickets/{ticket['id']}", headers=headers)).json()
    assert detail["sentiment"] is None


async def test_provider_failures_do_not_break_the_sweep(client, db_session, monkeypatch):
    _, key = await _workspace(client, email="sentimentfail@example.com")
    await _ticket(client, key)

    async def boom(workspace, *, system, messages, temperature=0.3, max_tokens=900):
        raise ai_service.AIError("provider down")

    monkeypatch.setattr(ai_service, "complete_chat", boom)
    assert await sentiment_svc.score_pending(db_session) == 0


async def test_analyze_classifies_and_parses_leniently(client, db_session, monkeypatch):
    await _workspace(client, email="sentimentlabel@example.com")
    workspace = (await db_session.execute(select(Workspace))).scalars().first()

    monkeypatch.setattr(ai_service, "complete_chat", _fake_reply("Positive."))
    assert await sentiment_svc.analyze(workspace, "thanks, that fixed it") == "positive"
    assert await sentiment_svc.analyze(workspace, "   ") is None

    assert sentiment_svc._parse("  NEGATIVE  ") == "negative"
    assert sentiment_svc._parse("neutral") == "neutral"
    assert sentiment_svc._parse("unsure") is None
