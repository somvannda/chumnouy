"""Knowledge base: seeded corpus, CRUD, filtering, soft-delete/restore, tenancy."""
import pytest

from app.services.knowledge import DEFAULT_ARTICLES

pytestmark = pytest.mark.asyncio


async def _signup(client, *, email, workspace="Acme Support"):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": workspace},
    )
    assert signup.status_code == 201, signup.text
    token = signup.json()["token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _key(client, token, *, scopes):
    headers = {"Authorization": f"Bearer {token}"}
    integration = await client.post(
        "/api/v1/integrations", json={"name": "App", "scopes": scopes}, headers=headers
    )
    return (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]


async def test_signup_seeds_the_default_corpus(client):
    _, headers = await _signup(client, email="seed@example.com")
    listing = await client.get("/api/v1/knowledge/articles", headers=headers)
    assert listing.status_code == 200, listing.text
    articles = listing.json()
    assert len(articles) == len(DEFAULT_ARTICLES)
    assert all(article["is_active"] for article in articles)
    assert {article["section"] for article in articles} == {"getting-started", "account", "billing"}


async def test_create_derives_and_deduplicates_slug(client):
    _, headers = await _signup(client, email="slug@example.com")
    first = await client.post(
        "/api/v1/knowledge/articles",
        json={"title": "Refund policy", "body": "Refunds take 3 days."},
        headers=headers,
    )
    assert first.status_code == 201, first.text
    assert first.json()["slug"] == "refund-policy"

    second = await client.post(
        "/api/v1/knowledge/articles",
        json={"title": "Refund policy", "body": "A second article."},
        headers=headers,
    )
    assert second.json()["slug"] == "refund-policy-2"


async def test_list_filters_and_search(client):
    _, headers = await _signup(client, email="filter@example.com")
    await client.post(
        "/api/v1/knowledge/articles",
        json={"title": "Khmer refund policy", "body": "សំណង", "locale": "km", "section": "billing"},
        headers=headers,
    )

    by_section = await client.get("/api/v1/knowledge/articles?section=billing", headers=headers)
    slugs = [a["slug"] for a in by_section.json()]
    assert "khmer-refund-policy" in slugs
    assert all(a["section"] == "billing" for a in by_section.json())

    by_locale = await client.get("/api/v1/knowledge/articles?locale=km", headers=headers)
    assert [a["locale"] for a in by_locale.json()] == ["km"]

    by_query = await client.get("/api/v1/knowledge/articles?q=refund", headers=headers)
    assert by_query.json()[0]["slug"] == "khmer-refund-policy"


async def test_update_and_restore(client):
    _, headers = await _signup(client, email="update@example.com")
    created = await client.post(
        "/api/v1/knowledge/articles",
        json={"title": "Old title", "body": "Body v1"},
        headers=headers,
    )
    article_id = created.json()["id"]

    updated = await client.patch(
        f"/api/v1/knowledge/articles/{article_id}",
        json={"title": "New title", "body": "Body v2", "is_active": False},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "New title"
    assert updated.json()["is_active"] is False

    inactive = await client.get("/api/v1/knowledge/articles?active=false", headers=headers)
    assert [a["id"] for a in inactive.json()] == [article_id]

    restored = await client.post(f"/api/v1/knowledge/articles/{article_id}/restore", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True


async def test_write_requires_scope(client):
    token, headers = await _signup(client, email="scope@example.com")
    key = await _key(client, token, scopes=["knowledge:read"])

    denied = await client.post(
        "/api/v1/knowledge/articles",
        json={"title": "No", "body": "nope"},
        headers={"X-Api-Key": key},
    )
    assert denied.status_code == 403

    allowed = await client.get("/api/v1/knowledge/articles", headers={"X-Api-Key": key})
    assert allowed.status_code == 200
    assert len(allowed.json()) == len(DEFAULT_ARTICLES)


async def test_articles_are_workspace_isolated(client):
    _, headers_a = await _signup(client, email="a@example.com", workspace="Workspace A")
    _, headers_b = await _signup(client, email="b@example.com", workspace="Workspace B")

    created = await client.post(
        "/api/v1/knowledge/articles",
        json={"title": "Only in A", "body": "secret"},
        headers=headers_a,
    )
    article_id = created.json()["id"]

    listing_b = await client.get("/api/v1/knowledge/articles", headers=headers_b)
    assert all(a["title"] != "Only in A" for a in listing_b.json())

    fetch_b = await client.get(f"/api/v1/knowledge/articles/{article_id}", headers=headers_b)
    assert fetch_b.status_code == 404
