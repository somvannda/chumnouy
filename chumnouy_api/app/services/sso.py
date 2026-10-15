"""Single sign-on (OIDC authorization-code flow).

A workspace configures an OIDC issuer (``workspace.settings.sso``): the app
redirects to ``/authorize``, and the callback exchanges the code, verifies the
ID token against the issuer's JWKS, checks the email domain, and issues a console
JWT (just-in-time provisioning the user + membership).
"""
from __future__ import annotations

import secrets
from urllib.parse import urlencode
from uuid import UUID

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Membership, User, Workspace
from app.schemas import AuthRead, UserRead, WorkspaceRead
from app.security import ALGORITHM, create_access_token, decode_token

STATE_TTL_MINUTES = 15


class SsoError(Exception):
    """A user-fixable SSO problem (bad config, bad response, disallowed domain)."""


def sso_config(workspace: Workspace) -> dict:
    return (workspace.settings or {}).get("sso") or {}


def sso_enabled(workspace: Workspace) -> bool:
    config = sso_config(workspace)
    return bool(config.get("enabled") and config.get("issuer") and config.get("client_id"))


def _issuer(config: dict) -> str:
    return str(config.get("issuer") or "").rstrip("/")


def redirect_uri() -> str:
    return f"{settings.api_public_url.rstrip('/')}/api/v1/auth/sso/callback"


def authorize_url(workspace: Workspace, *, state: str) -> str:
    config = sso_config(workspace)
    params = {
        "response_type": "code",
        "client_id": config.get("client_id", ""),
        "redirect_uri": redirect_uri(),
        "scope": "openid email profile",
        "state": state,
    }
    endpoint = config.get("authorize_url") or f"{_issuer(config)}/authorize"
    return f"{endpoint}?{urlencode(params)}"


def make_state(workspace: Workspace) -> str:
    payload = {
        "ws": str(workspace.id),
        "nonce": secrets.token_urlsafe(16),
        "type": "sso_state",
    }
    from datetime import datetime, timedelta, timezone

    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES)
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def parse_state(state: str) -> UUID:
    try:
        payload = decode_token(state)
        if payload.get("type") != "sso_state":
            raise ValueError("not an sso state")
        return UUID(payload["ws"])
    except (KeyError, ValueError, TypeError, jwt.PyJWTError) as exc:
        raise SsoError("Invalid or expired SSO state") from exc


async def _exchange_code(config: dict, code: str) -> dict:
    """Exchange the authorization code for tokens (OIDC token endpoint)."""
    token_url = config.get("token_url") or f"{_issuer(config)}/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
        "client_id": config.get("client_id", ""),
        "client_secret": config.get("client_secret", ""),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(token_url, data=data)
    except httpx.HTTPError as exc:
        raise SsoError(f"Could not reach the identity provider: {exc}") from exc
    if response.status_code >= 400:
        raise SsoError(f"The identity provider rejected the code ({response.status_code})")
    return response.json()


def _claims(id_token: str, config: dict) -> dict:
    """Verify the ID token against the issuer's JWKS and return its claims."""
    jwks_url = config.get("jwks_url") or f"{_issuer(config)}/.well-known/jwks.json"
    try:
        signing_key = jwt.PyJWKClient(jwks_url).get_signing_key_from_jwt(id_token)
        return jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=config.get("client_id"),
            issuer=_issuer(config),
        )
    except jwt.PyJWTError as exc:
        raise SsoError(f"Could not verify the identity token: {exc}") from exc


async def complete_login(db: AsyncSession, workspace: Workspace, code: str) -> AuthRead:
    config = sso_config(workspace)
    if not sso_enabled(workspace):
        raise SsoError("SSO is not enabled for this workspace")
    tokens = await _exchange_code(config, code)
    id_token = tokens.get("id_token")
    if not id_token:
        raise SsoError("The identity provider returned no id_token")
    claims = _claims(id_token, config)

    email = str(claims.get("email") or "").lower()
    if not email:
        raise SsoError("The identity token had no email")
    domains = config.get("allowed_domains") or []
    if domains and email.split("@")[-1] not in domains:
        raise SsoError("Your email domain is not allowed for this workspace")

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            name=str(claims.get("name") or email.split("@")[0]),
            password_hash="!sso",  # no password login; SSO only
            is_verified=True,
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
