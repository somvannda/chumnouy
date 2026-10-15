"""Rich-text messages: HTML is stored sanitised; text is stored verbatim."""
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


def _body(message, **extra):
    payload = {"subject": "Rich", "message": message, "requester": {"external_id": "c1"}}
    payload.update(extra)
    return payload


async def test_html_opening_message_is_sanitised(client):
    _, key = await _workspace(client, email="rich1@example.com")
    resp = await client.post(
        "/api/v1/tickets",
        json=_body(
            "<p>Hello <strong>there</strong></p><script>alert(1)</script>"
            "<a href=\"javascript:alert(1)\">x</a><img src=x onerror=alert(1)>",
            message_format="html",
        ),
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 201, resp.text
    message = resp.json()["messages"][0]
    assert message["body_format"] == "html"
    assert "<strong>there</strong>" in message["body"]
    lowered = message["body"].lower()
    assert "<script" not in lowered
    assert "javascript:" not in lowered
    assert "<img" not in lowered
    assert "onerror" not in lowered


async def test_text_messages_are_stored_verbatim(client):
    _, key = await _workspace(client, email="rich2@example.com")
    resp = await client.post(
        "/api/v1/tickets", json=_body("<b>not html</b> & fine"), headers={"X-Api-Key": key}
    )
    message = resp.json()["messages"][0]
    assert message["body_format"] == "text"
    assert message["body"] == "<b>not html</b> & fine"


async def test_html_reply_is_sanitised(client):
    headers, key = await _workspace(client, email="rich3@example.com")
    ticket_id = (
        await client.post("/api/v1/tickets", json=_body("plain"), headers={"X-Api-Key": key})
    ).json()["id"]

    reply = await client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        json={"body": "<em>ok</em><img src=x onerror=alert(1)>", "body_format": "html"},
        headers=headers,
    )
    assert reply.status_code == 201, reply.text
    body = reply.json()
    assert body["body_format"] == "html"
    assert "<em>ok</em>" in body["body"]
    assert "<img" not in body["body"].lower()
