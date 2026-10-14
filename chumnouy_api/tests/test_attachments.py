"""Attachment staging and claim (ported from Chmaba POS).

Files are uploaded unowned, then claimed by ticket creation, a reply, or
``POST /tickets/{id}/attachments``. The security-critical guarantees under test
are tenant isolation (a foreign id is rejected) and single-claim (a claimed id
cannot be claimed again).
"""
import pytest

from app.config import settings

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _media_root(tmp_path, monkeypatch):
    """Keep uploads out of the repo: media lives in the test's tmp dir."""
    monkeypatch.setattr(settings, "media_root", str(tmp_path / "media"))


async def _workspace_with_key(client, *, email, workspace="Acme Support", scopes=None):
    scopes = scopes or ["tickets:read", "tickets:write"]
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
    )
    assert signup.status_code == 201, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}
    integration = await client.post(
        "/api/v1/integrations", json={"name": "Chmaba POS", "scopes": scopes}, headers=headers
    )
    assert integration.status_code == 201, integration.text
    key_resp = await client.post(
        f"/api/v1/integrations/{integration.json()['id']}/keys",
        json={"name": "k", "environment": "live"},
        headers=headers,
    )
    assert key_resp.status_code == 201, key_resp.text
    return signup.json()["token"], key_resp.json()["key"]


async def _upload(client, key, *, name="receipt.png", content=b"\x89PNG-fake-bytes"):
    return await client.post(
        "/api/v1/uploads",
        files={"file": (name, content, "image/png")},
        headers={"X-Api-Key": key},
    )


def _ticket_body(*, attachment_ids=None):
    body = {
        "subject": "Card reader not charging",
        "message": "The terminal stopped charging this morning.",
        "requester": {"external_id": "cust_1", "name": "Sok Dara", "email": "dara@example.com"},
    }
    if attachment_ids is not None:
        body["attachment_ids"] = attachment_ids
    return body


async def test_upload_stages_an_unowned_attachment(client):
    _, key = await _workspace_with_key(client, email="up@example.com")
    resp = await _upload(client, key, name="receipt.png")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["url"].startswith("/media/workspaces/")
    assert body["original_filename"] == "receipt.png"
    assert body["content_type"] == "image/png"
    assert body["byte_size"] > 0


async def test_identical_bytes_deduplicate(client):
    _, key = await _workspace_with_key(client, email="dedupe@example.com")
    first = await _upload(client, key, content=b"same-bytes")
    second = await _upload(client, key, content=b"same-bytes")
    assert first.json()["url"] == second.json()["url"]


async def test_create_ticket_claims_opening_attachments(client):
    _, key = await _workspace_with_key(client, email="create@example.com")
    staged = (await _upload(client, key)).json()

    created = await client.post(
        "/api/v1/tickets", json=_ticket_body(attachment_ids=[staged["id"]]), headers={"X-Api-Key": key}
    )
    assert created.status_code == 201, created.text
    body = created.json()
    # Opening-question files sit at the ticket level, not on the first message.
    assert [a["id"] for a in body["attachments"]] == [staged["id"]]
    assert body["messages"][0]["attachments"] == []

    detail = await client.get(f"/api/v1/tickets/{body['id']}", headers={"X-Api-Key": key})
    assert [a["id"] for a in detail.json()["attachments"]] == [staged["id"]]


async def test_reply_claim_attaches_to_the_message(client):
    token, key = await _workspace_with_key(client, email="reply@example.com")
    created = await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})
    ticket_id = created.json()["id"]
    staged = (await _upload(client, key)).json()

    reply = await client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        json={"body": "Here is the photo.", "attachment_ids": [staged["id"]]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reply.status_code == 201, reply.text
    assert [a["id"] for a in reply.json()["attachments"]] == [staged["id"]]

    detail = await client.get(f"/api/v1/tickets/{ticket_id}", headers={"Authorization": f"Bearer {token}"})
    assert detail.json()["attachments"] == []
    assert [a["id"] for a in detail.json()["messages"][-1]["attachments"]] == [staged["id"]]


async def test_claim_endpoint_attaches_to_the_ticket(client):
    token, key = await _workspace_with_key(client, email="claim@example.com")
    created = await client.post("/api/v1/tickets", json=_ticket_body(), headers={"X-Api-Key": key})
    ticket_id = created.json()["id"]
    staged = (await _upload(client, key)).json()

    claimed = await client.post(
        f"/api/v1/tickets/{ticket_id}/attachments",
        json={"attachment_ids": [staged["id"]]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert claimed.status_code == 201, claimed.text
    assert [a["id"] for a in claimed.json()] == [staged["id"]]


async def test_foreign_attachment_is_rejected(client):
    _, key_a = await _workspace_with_key(client, email="a@example.com", workspace="Workspace A")
    _, key_b = await _workspace_with_key(client, email="b@example.com", workspace="Workspace B")
    staged = (await _upload(client, key_a)).json()

    denied = await client.post(
        "/api/v1/tickets", json=_ticket_body(attachment_ids=[staged["id"]]), headers={"X-Api-Key": key_b}
    )
    assert denied.status_code == 400


async def test_attachment_cannot_be_claimed_twice(client):
    token, key = await _workspace_with_key(client, email="twice@example.com")
    staged = (await _upload(client, key)).json()
    created = await client.post(
        "/api/v1/tickets", json=_ticket_body(attachment_ids=[staged["id"]]), headers={"X-Api-Key": key}
    )
    ticket_id = created.json()["id"]

    again = await client.post(
        f"/api/v1/tickets/{ticket_id}/attachments",
        json={"attachment_ids": [staged["id"]]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert again.status_code == 400


async def test_too_many_attachments_are_rejected(client):
    _, key = await _workspace_with_key(client, email="limit@example.com")
    ids = []
    for i in range(settings.max_attachments_per_message + 1):
        ids.append((await _upload(client, key, content=f"bytes-{i}".encode())).json()["id"])

    denied = await client.post(
        "/api/v1/tickets", json=_ticket_body(attachment_ids=ids), headers={"X-Api-Key": key}
    )
    assert denied.status_code == 400


async def test_unsupported_type_is_rejected(client):
    _, key = await _workspace_with_key(client, email="type@example.com")
    resp = await client.post(
        "/api/v1/uploads",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 400


async def test_upload_requires_write_scope(client):
    _, key = await _workspace_with_key(client, email="scope@example.com", scopes=["tickets:read"])
    resp = await _upload(client, key)
    assert resp.status_code == 403
