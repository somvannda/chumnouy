"""SAML 2.0 service provider (SP) sign-in.

A workspace configures its IdP under ``workspace.settings["saml"]``: the SSO URL,
the IdP signing certificate (PEM) and the attributes carrying email/name. An ACS
response is verified with ``signxml`` against that certificate — unsigned or
tampered responses are rejected — and then the user is JIT-provisioned (created
with an unusable password) and signed in.

OIDC lives in ``services/sso.py``; this is the SAML counterpart.
"""
from __future__ import annotations

import base64
import secrets

from lxml import etree
from signxml import XMLVerifier
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Membership, User, Workspace
from app.schemas import AuthRead, SamlStart, UserRead, WorkspaceRead
from app.security import create_access_token, hash_password

SAML_ASSERTION = "urn:oasis:names:tc:SAML:2.0:assertion"
SAML_PROTOCOL = "urn:oasis:names:tc:SAML:2.0:protocol"
SAML_METADATA = "urn:oasis:names:tc:SAML:2.0:metadata"


class SamlError(Exception):
    """Base class for SAML problems (mapped to a 4xx by the router)."""


class SamlNotConfigured(SamlError):
    pass


class SamlInvalid(SamlError):
    pass


def saml_config(workspace: Workspace) -> dict:
    return (workspace.settings or {}).get("saml") or {}


def saml_enabled(workspace: Workspace) -> bool:
    config = saml_config(workspace)
    return bool(config.get("enabled") and config.get("idp_sso_url") and config.get("idp_certificate"))


def sp_entity_id(workspace: Workspace) -> str:
    return saml_config(workspace).get("sp_entity_id") or f"chumnouy:{workspace.slug}"


def acs_url(base_url: str, workspace: Workspace) -> str:
    return f"{base_url.rstrip('/')}/api/v1/auth/saml/{workspace.slug}/acs"


def start(workspace: Workspace, base_url: str) -> SamlStart:
    if not saml_enabled(workspace):
        raise SamlNotConfigured("SAML is not configured for this workspace")
    return SamlStart(
        sso_url=saml_config(workspace)["idp_sso_url"],
        entity_id=sp_entity_id(workspace),
        acs_url=acs_url(base_url, workspace),
    )


def metadata(workspace: Workspace, base_url: str) -> str:
    """SP metadata the IdP administrator pastes into their configuration."""
    entity = etree.Element(
        f"{{{SAML_METADATA}}}EntityDescriptor",
        nsmap={"md": SAML_METADATA},
        entityID=sp_entity_id(workspace),
    )
    service = etree.SubElement(
        entity,
        f"{{{SAML_METADATA}}}SPSSODescriptor",
        protocolSupportEnumeration=SAML_PROTOCOL,
    )
    etree.SubElement(
        service,
        f"{{{SAML_METADATA}}}AssertionConsumerService",
        Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
        Location=acs_url(base_url, workspace),
        index="0",
    )
    return etree.tostring(entity, xml_declaration=True, encoding="utf-8").decode("utf-8")


def _attribute_values(root, name: str) -> list[str]:
    values: list[str] = []
    for attribute in root.iter(f"{{{SAML_ASSERTION}}}Attribute"):
        if attribute.get("Name") != name:
            continue
        for value in attribute.iter(f"{{{SAML_ASSERTION}}}AttributeValue"):
            if value.text:
                values.append(value.text)
    return values


def verify(workspace: Workspace, saml_response: str) -> dict:
    """Verify the response signature and return ``{"email", "name"}``.

    Raises :class:`SamlInvalid` for anything that is not a signed, well-formed
    assertion from the configured IdP.
    """
    config = saml_config(workspace)
    certificate = config.get("idp_certificate")
    if not certificate:
        raise SamlNotConfigured("SAML is not configured for this workspace")
    try:
        payload = base64.b64decode(saml_response, validate=True)
    except Exception as exc:  # noqa: BLE001 - any decode failure is a bad request
        raise SamlInvalid("The SAML response is not valid base64") from exc
    try:
        verified = XMLVerifier().verify(payload, x509_cert=certificate)
    except Exception as exc:  # noqa: BLE001 - InvalidSignature and friends
        raise SamlInvalid("The SAML response signature could not be verified") from exc

    root = verified.signed_xml
    if root is None:
        raise SamlInvalid("The SAML response carried no signed content")

    email_attribute = config.get("email_attribute") or "email"
    name_attribute = config.get("name_attribute")
    email = next(iter(_attribute_values(root, email_attribute)), None)
    name = _attribute_values(root, name_attribute)[0] if name_attribute else None
    if not email:
        email = next((node.text for node in root.iter(f"{{{SAML_ASSERTION}}}NameID")), None)
    if not email:
        raise SamlInvalid("The SAML response did not carry an email address")

    email = email.strip().lower()
    allowed = [domain.strip().lower() for domain in (config.get("allowed_domains") or [])]
    if allowed and email.rsplit("@", 1)[-1] not in allowed:
        raise SamlInvalid("This email domain is not allowed for this workspace")
    return {"email": email, "name": (name or email.split("@")[0]).strip()}


async def login(db: AsyncSession, workspace: Workspace, saml_response: str) -> AuthRead:
    """Verify an ACS response and sign the (JIT-provisioned) user in."""
    claims = verify(workspace, saml_response)
    email = claims["email"]

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        # No usable password: the account can only be entered through the IdP.
        user = User(
            email=email,
            name=claims["name"],
            password_hash=hash_password(secrets.token_urlsafe(32)),
        )
        db.add(user)
        await db.flush()

    membership = (
        await db.execute(
            select(Membership).where(
                Membership.workspace_id == workspace.id, Membership.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        membership = Membership(workspace_id=workspace.id, user_id=user.id, role="agent")
        db.add(membership)
    await db.commit()
    await db.refresh(user)
    return AuthRead(
        token=create_access_token(user.id),
        user=UserRead.model_validate(user),
        workspace=WorkspaceRead(
            id=workspace.id, name=workspace.name, slug=workspace.slug, role=membership.role
        ),
    )
