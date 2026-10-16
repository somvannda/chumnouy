"""Help-centre article feedback ("was this helpful?")."""
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


async def _article(client, headers, *, title="Refund policy"):
    created = await client.post(
        "/api/v1/knowledge/articles",
        json={"title": title, "body": "Refunds take three days."},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    return created.json()


async def test_feedback_is_recorded_and_counted(client):
    slug, headers = await _workspace(client, "feedback@example.com")
    article = await _article(client, headers)

    # A fresh article has no verdicts.
    fresh = (await client.get(f"/api/v1/public/help/{slug}/articles/{article['slug']}")).json()
    assert fresh["helpful_yes"] == 0
    assert fresh["helpful_no"] == 0

    posted = await client.post(
        f"/api/v1/public/help/{slug}/articles/{article['slug']}/feedback",
        json={"helpful": True},
    )
    assert posted.status_code == 201, posted.text
    assert posted.json()["helpful"] is True
    assert posted.json()["comment"] is None

    await client.post(
        f"/api/v1/public/help/{slug}/articles/{article['slug']}/feedback",
        json={"helpful": False, "comment": "  Out of date.  "},
        headers=None,
    )
    await client.post(
        f"/api/v1/public/help/{slug}/articles/{article['slug']}/feedback",
        json={"helpful": True},
    )

    counted = (await client.get(f"/api/v1/public/help/{slug}/articles/{article['slug']}")).json()
    assert counted["helpful_yes"] == 2
    assert counted["helpful_no"] == 1


async def test_feedback_rejects_unknown_articles(client):
    slug, _ = await _workspace(client, "feedback404@example.com")
    missing = await client.post(
        f"/api/v1/public/help/{slug}/articles/not-a-real-article/feedback",
        json={"helpful": True},
    )
    assert missing.status_code == 404

    no_workspace = await client.post(
        "/api/v1/public/help/nope/articles/anything/feedback", json={"helpful": True}
    )
    assert no_workspace.status_code == 404


async def test_feedback_is_scoped_to_the_article_and_workspace(client):
    slug_a, headers_a = await _workspace(client, "feedbacka@example.com", "Workspace A")
    slug_b, headers_b = await _workspace(client, "feedbackb@example.com", "Workspace B")
    first = await _article(client, headers_a, title="A article")
    second = await _article(client, headers_a, title="B article")
    other = await _article(client, headers_b, title="Other workspace")

    await client.post(
        f"/api/v1/public/help/{slug_a}/articles/{first['slug']}/feedback", json={"helpful": False}
    )

    untouched = (await client.get(f"/api/v1/public/help/{slug_a}/articles/{second['slug']}")).json()
    assert untouched["helpful_yes"] == 0
    assert untouched["helpful_no"] == 0

    foreign = (
        await client.get(f"/api/v1/public/help/{slug_b}/articles/{other['slug']}")
    ).json()
    assert foreign["helpful_yes"] == 0
    assert foreign["helpful_no"] == 0
