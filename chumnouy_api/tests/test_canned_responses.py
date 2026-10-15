"""Canned responses: CRUD, sanitisation, scope and tenancy."""
import pytest

pytestmark = pytest.mark.asyncio


async def _workspace(client, *, email, workspace="Acme Support", scopes=("tickets:read", "tickets:write")):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
    )
    assert signup.status_code == 201, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}
    integration = await client.post(
        "/api/v1/integrations", json={"name": "POS", "scopes": list(scopes)}, headers=headers
    )
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]
    return headers, key


async def test_canned_response_crud(client):
    headers, _ = await _workspace(client, email="canned@example.com")

    created = await client.post(
        "/api/v1/canned-responses",
        json={"title": "Thanks", "body": "Thanks for reaching out!"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    canned_id = created.json()["id"]
    assert created.json()["title"] == "Thanks"

    listed = await client.get("/api/v1/canned-responses", headers=headers)
    assert [c["id"] for c in listed.json()] == [canned_id]

    fetched = await client.get(f"/api/v1/canned-responses/{canned_id}", headers=headers)
    assert fetched.json()["body"] == "Thanks for reaching out!"

    patched = await client.patch(
        f"/api/v1/canned-responses/{canned_id}", json={"title": "Thank you"}, headers=headers
    )
    assert patched.json()["title"] == "Thank you"

    deleted = await client.delete(f"/api/v1/canned-responses/{canned_id}", headers=headers)
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/canned-responses", headers=headers)).json() == []


async def test_html_canned_response_is_sanitised(client):
    headers, _ = await _workspace(client, email="cannedhtml@example.com")
    created = await client.post(
        "/api/v1/canned-responses",
        json={"title": "Rich", "body": "<p>Hi <b>there</b></p><script>alert(1)</script>", "body_format": "html"},
        headers=headers,
    )
    body = created.json()
    assert body["body_format"] == "html"
    assert "<b>there</b>" in body["body"]
    assert "<script" not in body["body"].lower()


async def test_canned_response_requires_write_scope(client):
    _, key = await _workspace(client, email="cannedscope@example.com", scopes=("tickets:read",))
    denied = await client.post(
        "/api/v1/canned-responses", json={"title": "Nope", "body": "x"}, headers={"X-Api-Key": key}
    )
    assert denied.status_code == 403
    assert (await client.get("/api/v1/canned-responses", headers={"X-Api-Key": key})).status_code == 200


async def test_canned_responses_are_workspace_isolated(client):
    headers_a, _ = await _workspace(client, email="a@example.com", workspace="Workspace A")
    headers_b, _ = await _workspace(client, email="b@example.com", workspace="Workspace B")
    canned_id = (
        await client.post(
            "/api/v1/canned-responses", json={"title": "Only A", "body": "x"}, headers=headers_a
        )
    ).json()["id"]

    assert (await client.get("/api/v1/canned-responses", headers=headers_b)).json() == []
    assert (await client.get(f"/api/v1/canned-responses/{canned_id}", headers=headers_b)).status_code == 404
