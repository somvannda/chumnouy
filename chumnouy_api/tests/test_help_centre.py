"""Public help centre: unauthenticated, active-only, workspace-scoped by slug."""
import pytest

pytestmark = pytest.mark.asyncio


async def _workspace(client, email, workspace="Acme Support"):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
    )
    assert signup.status_code == 201, signup.text
    data = signup.json()
    return data["workspace"]["slug"], {"Authorization": f"Bearer {data['token']}"}


async def test_help_centre_is_public_and_lists_the_corpus(client):
    slug, _ = await _workspace(client, "help@example.com")
    resp = await client.get(f"/api/v1/public/help/{slug}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["workspace"] == slug
    assert body["articles"]
    assert body["sections"] and all(s["count"] > 0 for s in body["sections"])


async def test_help_article_detail_and_deactivation(client):
    slug, headers = await _workspace(client, "help2@example.com")
    created = await client.post(
        "/api/v1/knowledge/articles",
        json={"title": "Refund policy", "body": "Refunds take three days."},
        headers=headers,
    )
    article = created.json()

    detail = await client.get(f"/api/v1/public/help/{slug}/articles/{article['slug']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["title"] == "Refund policy"

    await client.patch(
        f"/api/v1/knowledge/articles/{article['id']}", json={"is_active": False}, headers=headers
    )
    gone = await client.get(f"/api/v1/public/help/{slug}/articles/{article['slug']}")
    assert gone.status_code == 404
    assert article["slug"] not in [
        a["slug"] for a in (await client.get(f"/api/v1/public/help/{slug}")).json()["articles"]
    ]


async def test_help_search(client):
    slug, headers = await _workspace(client, "help3@example.com")
    await client.post(
        "/api/v1/knowledge/articles",
        json={"title": "Refund policy", "body": "Refunds take three days."},
        headers=headers,
    )
    hit = await client.get(f"/api/v1/public/help/{slug}?q=refund")
    assert any(a["slug"] == "refund-policy" for a in hit.json()["articles"])
    miss = await client.get(f"/api/v1/public/help/{slug}?q=zzzznotfound")
    assert miss.json()["articles"] == []


async def test_help_centre_unknown_workspace(client):
    assert (await client.get("/api/v1/public/help/does-not-exist")).status_code == 404
