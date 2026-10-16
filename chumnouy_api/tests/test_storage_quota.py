"""Storage quota: a workspace can cap the bytes it stores."""
import pytest
from sqlalchemy import select

from app.config import settings
from app.models import Workspace

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _media_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "media_root", str(tmp_path / "media"))


async def _key(client, *, email):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": "Acme"},
    )
    assert signup.status_code == 201, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}
    integration = await client.post(
        "/api/v1/integrations",
        json={"name": "POS", "scopes": ["tickets:write", "tickets:read"]},
        headers=headers,
    )
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]
    return key


async def _set_quota(db_session, storage_mb):
    workspace = (await db_session.execute(select(Workspace))).scalars().first()
    workspace.settings = {**(workspace.settings or {}), "quota": {"storage_mb": storage_mb}}
    await db_session.commit()


async def _upload(client, key, *, name="receipt.png", content=b"\x89PNG-fake-bytes"):
    return await client.post(
        "/api/v1/uploads",
        files={"file": (name, content, "image/png")},
        headers={"X-Api-Key": key},
    )


async def test_uploads_are_unlimited_without_a_quota(client):
    key = await _key(client, email="storagefree@example.com")
    assert (await _upload(client, key)).status_code == 201
    assert (await _upload(client, key, name="second.png")).status_code == 201


async def test_storage_quota_blocks_uploads_over_the_cap(client, db_session):
    key = await _key(client, email="storagecap@example.com")
    # 1 MB is plenty for one small file, but not for an oversized one.
    await _set_quota(db_session, 1)

    assert (await _upload(client, key)).status_code == 201

    big = await _upload(client, key, name="big.png", content=b"x" * (1024 * 1024 + 1))
    assert big.status_code == 413
    assert big.json()["error"]["message"] == "Storage quota reached"
