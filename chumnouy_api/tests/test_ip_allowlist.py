"""IP allowlist: sign-in can be restricted to a network."""
import pytest

pytestmark = pytest.mark.asyncio

PASSWORD = "supersecret123"


async def _owner(client, *, email):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": PASSWORD, "name": "Owner", "workspace_name": "Acme"},
    )
    assert signup.status_code == 201, signup.text
    return {"Authorization": f"Bearer {signup.json()['token']}"}


async def _login(client, email, *, forwarded_for=None):
    headers = {"X-Forwarded-For": forwarded_for} if forwarded_for else {}
    return await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}, headers=headers
    )


async def test_login_is_unrestricted_by_default(client):
    headers = await _owner(client, email="ipfree@example.com")
    settings = (await client.get("/api/v1/console/settings", headers=headers)).json()
    assert settings["security"]["ip_allowlist"] == []

    assert (await _login(client, "ipfree@example.com", forwarded_for="8.8.8.8")).status_code == 200
    assert (await _login(client, "ipfree@example.com")).status_code == 200


async def test_allowlist_restricts_sign_in(client):
    headers = await _owner(client, email="ipcap@example.com")

    updated = await client.patch(
        "/api/v1/console/settings/security",
        json={"ip_allowlist": ["10.0.0.0/8", "192.168.1.5"]},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["security"]["ip_allowlist"] == ["10.0.0.0/8", "192.168.1.5"]

    assert (await _login(client, "ipcap@example.com", forwarded_for="10.1.2.3")).status_code == 200
    assert (await _login(client, "ipcap@example.com", forwarded_for="192.168.1.5")).status_code == 200

    blocked = await _login(client, "ipcap@example.com", forwarded_for="8.8.8.8")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["message"] == "Sign-in is not allowed from this network"


async def test_allowlist_drops_entries_that_are_not_networks(client):
    headers = await _owner(client, email="ipbad@example.com")
    updated = await client.patch(
        "/api/v1/console/settings/security",
        json={"ip_allowlist": ["not-an-ip", "10.0.0.1", "   "]},
        headers=headers,
    )
    assert updated.json()["security"]["ip_allowlist"] == ["10.0.0.1"]


async def test_allowlist_change_is_audited(client):
    headers = await _owner(client, email="ipaudit@example.com")
    await client.patch(
        "/api/v1/console/settings/security",
        json={"ip_allowlist": ["10.0.0.1"]},
        headers=headers,
    )
    events = (await client.get("/api/v1/audit/workspace?type=settings.security", headers=headers)).json()
    assert events["data"][0]["data"] == {"ip_allowlist": ["10.0.0.1"]}


async def test_clearing_the_allowlist_restores_open_sign_in(client):
    headers = await _owner(client, email="ipclear@example.com")
    await client.patch(
        "/api/v1/console/settings/security",
        json={"ip_allowlist": ["10.0.0.0/8"]},
        headers=headers,
    )
    assert (await _login(client, "ipclear@example.com", forwarded_for="8.8.8.8")).status_code == 403

    await client.patch(
        "/api/v1/console/settings/security", json={"ip_allowlist": []}, headers=headers
    )
    assert (await _login(client, "ipclear@example.com", forwarded_for="8.8.8.8")).status_code == 200
