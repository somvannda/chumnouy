"""SAML 2.0 SP: metadata, the IdP hand-off and the verified ACS callback."""
import base64
import datetime as dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree
from signxml import XMLSigner

pytestmark = pytest.mark.asyncio

RESPONSE_TEMPLATE = (
    '<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"'
    ' xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" ID="_response" Version="2.0">'
    "  <saml:Issuer>https://idp.example.com</saml:Issuer>"
    '  <saml:Assertion ID="_assertion" Version="2.0">'
    "    <saml:Issuer>https://idp.example.com</saml:Issuer>"
    "    <saml:Subject>"
    "      <saml:NameID>{name_id}</saml:NameID>"
    "    </saml:Subject>"
    "    <saml:AttributeStatement>"
    '      <saml:Attribute Name="email">'
    "        <saml:AttributeValue>{email}</saml:AttributeValue>"
    "      </saml:Attribute>"
    '      <saml:Attribute Name="name">'
    "        <saml:AttributeValue>{name}</saml:AttributeValue>"
    "      </saml:Attribute>"
    "    </saml:AttributeStatement>"
    "  </saml:Assertion>"
    "</samlp:Response>"
)


def _key_and_certificate():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "idp.example.com")])
    now = dt.datetime.now(dt.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM).decode()
    return key_pem, cert_pem


def _signed_response(key_pem, cert_pem, *, email="new-agent@example.com", name="New Agent"):
    xml = RESPONSE_TEMPLATE.format(name_id=email, email=email, name=name)
    root = etree.fromstring(xml.encode("utf-8"))
    signed = XMLSigner().sign(root, key=key_pem, cert=cert_pem)
    return base64.b64encode(etree.tostring(signed)).decode("ascii")


async def _workspace(client, *, email, saml=None):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "name": "Owner", "workspace_name": "Acme"},
    )
    assert signup.status_code == 201, signup.text
    data = signup.json()
    headers = {"Authorization": f"Bearer {data['token']}"}
    slug = data["workspace"]["slug"]
    if saml is not None:
        updated = await client.patch(
            "/api/v1/console/settings/saml", json=saml, headers=headers
        )
        assert updated.status_code == 200, updated.text
    return slug, headers


async def test_acs_provisions_and_signs_in(client):
    key_pem, cert_pem = _key_and_certificate()
    slug, headers = await _workspace(
        client,
        email="saml@example.com",
        saml={
            "enabled": True,
            "idp_sso_url": "https://idp.example.com/sso",
            "idp_certificate": cert_pem,
            "email_attribute": "email",
            "name_attribute": "name",
        },
    )

    settings = (await client.get("/api/v1/console/settings", headers=headers)).json()["saml"]
    assert settings["enabled"] is True
    assert settings["idp_certificate_set"] is True
    assert "idp_certificate" not in settings  # the certificate itself is write-only

    started = await client.get(f"/api/v1/auth/saml/{slug}/start")
    assert started.status_code == 200, started.text
    assert started.json()["sso_url"] == "https://idp.example.com/sso"
    assert started.json()["acs_url"].endswith(f"/api/v1/auth/saml/{slug}/acs")

    response = await client.post(
        f"/api/v1/auth/saml/{slug}/acs",
        data={"SAMLResponse": _signed_response(key_pem, cert_pem)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] == "new-agent@example.com"
    assert body["user"]["name"] == "New Agent"
    assert body["workspace"]["role"] == "agent"

    # The provisioned member shows up on the roster, and their token works.
    roster = (await client.get("/api/v1/members", headers=headers)).json()
    assert "new-agent@example.com" in [member["email"] for member in roster]
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['token']}"}
    )
    assert me.status_code == 200


async def test_tampered_response_is_rejected(client):
    key_pem, cert_pem = _key_and_certificate()
    slug, _ = await _workspace(
        client,
        email="samltamper@example.com",
        saml={"enabled": True, "idp_sso_url": "https://idp.example.com/sso", "idp_certificate": cert_pem},
    )

    signed = _signed_response(key_pem, cert_pem, email="victim@example.com")
    raw = base64.b64decode(signed).decode("utf-8")
    tampered = base64.b64encode(raw.replace("victim@example.com", "attacker@example.com").encode())

    rejected = await client.post(
        f"/api/v1/auth/saml/{slug}/acs", data={"SAMLResponse": tampered.decode("ascii")}
    )
    assert rejected.status_code == 400
    assert "signature" in rejected.json()["error"]["message"]

    garbage = await client.post(
        f"/api/v1/auth/saml/{slug}/acs", data={"SAMLResponse": "not-base64!!"}
    )
    assert garbage.status_code == 400


async def test_acs_rejects_another_idps_certificate(client):
    _, cert_pem = _key_and_certificate()
    other_key, _ = _key_and_certificate()
    slug, _ = await _workspace(
        client,
        email="samlwrongidp@example.com",
        saml={"enabled": True, "idp_sso_url": "https://idp.example.com/sso", "idp_certificate": cert_pem},
    )

    response = await client.post(
        f"/api/v1/auth/saml/{slug}/acs",
        data={"SAMLResponse": _signed_response(other_key, cert_pem)},
    )
    assert response.status_code == 400


async def test_allowed_domains_are_enforced(client):
    key_pem, cert_pem = _key_and_certificate()
    slug, _ = await _workspace(
        client,
        email="samldomains@example.com",
        saml={
            "enabled": True,
            "idp_sso_url": "https://idp.example.com/sso",
            "idp_certificate": cert_pem,
            "allowed_domains": ["acme.com"],
        },
    )

    denied = await client.post(
        f"/api/v1/auth/saml/{slug}/acs",
        data={"SAMLResponse": _signed_response(key_pem, cert_pem, email="someone@other.com")},
    )
    assert denied.status_code == 400
    assert "domain" in denied.json()["error"]["message"]

    allowed = await client.post(
        f"/api/v1/auth/saml/{slug}/acs",
        data={"SAMLResponse": _signed_response(key_pem, cert_pem, email="someone@acme.com")},
    )
    assert allowed.status_code == 200, allowed.text


async def test_saml_endpoints_404_until_enabled(client):
    key_pem, cert_pem = _key_and_certificate()
    slug, headers = await _workspace(client, email="samloff@example.com")

    assert (await client.get(f"/api/v1/auth/saml/{slug}/start")).status_code == 404
    assert (await client.get(f"/api/v1/auth/saml/{slug}/metadata")).status_code == 404
    off = await client.post(
        f"/api/v1/auth/saml/{slug}/acs",
        data={"SAMLResponse": _signed_response(key_pem, cert_pem)},
    )
    assert off.status_code == 404

    await client.patch(
        "/api/v1/console/settings/saml",
        json={"enabled": True, "idp_sso_url": "https://idp.example.com/sso", "idp_certificate": cert_pem},
        headers=headers,
    )
    metadata = await client.get(f"/api/v1/auth/saml/{slug}/metadata")
    assert metadata.status_code == 200, metadata.text
    assert f"/api/v1/auth/saml/{slug}/acs" in metadata.text
    assert "AssertionConsumerService" in metadata.text

    events = (
        await client.get("/api/v1/audit/workspace?type=settings.saml", headers=headers)
    ).json()["data"]
    assert events and events[0]["data"]["enabled"] is True
