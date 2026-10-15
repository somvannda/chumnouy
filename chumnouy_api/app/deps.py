"""Authentication and workspace resolution.

Credentials resolve to a workspace context (docs/tenancy.md):

* **User JWT** (console) → :func:`get_current_user` / :func:`get_workspace_context`
* **API key** (machine)  → :func:`get_integration_context`
* **Either**             → :func:`get_tenant_context` (:class:`TenantContext`)

Every service function takes a ``workspace_id``; it is never read from the
request body, so a caller cannot address another workspace.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import ApiKey, Integration, Membership, Requester, User, Workspace, utcnow
from app.permissions import has_permission
from app.security import decode_token, hash_api_key

bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

# A signed-in console user may do anything within their workspace; API keys are
# limited to the scopes granted on the key.
CONSOLE_SCOPES: frozenset[str] = frozenset(
    {
        "tickets:read",
        "tickets:write",
        "requesters:read",
        "requesters:write",
        "knowledge:read",
        "knowledge:write",
        "assistant:use",
        "webhooks:manage",
    }
)


# --- Console (user JWT) -------------------------------------------------------


async def _load_user_from_token(db: AsyncSession, token: str) -> User:
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise ValueError("not an access token")
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError, TypeError, jwt.PyJWTError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    user = (
        await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise _UNAUTHORIZED
    return await _load_user_from_token(db, credentials.credentials)


async def _resolve_workspace(
    db: AsyncSession, user: User, workspace_id: UUID | None
) -> tuple[Membership, Workspace]:
    rows = (
        await db.execute(
            select(Membership, Workspace)
            .join(Workspace, Workspace.id == Membership.workspace_id)
            .where(
                Membership.user_id == user.id,
                Membership.status == "active",
                Workspace.is_active.is_(True),
            )
            .order_by(Membership.created_at)
        )
    ).all()
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Set up a workspace before using this feature",
        )
    if workspace_id is not None:
        for membership, workspace in rows:
            if workspace.id == workspace_id:
                return membership, workspace
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    if len(rows) == 1:
        return rows[0]
    owners = [row for row in rows if row[0].role == "owner"]
    if owners:
        return owners[0]
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="You belong to more than one workspace. Choose one with the X-Workspace-ID header",
    )


@dataclass
class WorkspaceContext:
    user: User
    workspace: Workspace
    membership: Membership
    roles: set[str] = field(default_factory=set)


async def get_workspace_context(
    user: User = Depends(get_current_user),
    workspace_id: UUID | None = Header(default=None, alias="X-Workspace-ID"),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceContext:
    membership, workspace = await _resolve_workspace(db, user, workspace_id)
    return WorkspaceContext(user=user, workspace=workspace, membership=membership)


def require_workspace_roles(*allowed_roles: str):
    """Allow the request only when the member's role is in ``allowed_roles``."""

    async def dependency(ctx: WorkspaceContext = Depends(get_workspace_context)) -> WorkspaceContext:
        if ctx.membership.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role cannot perform this action",
            )
        return ctx

    return dependency


def require_permission(action: str):
    """Allow the request only when the member's role grants ``action``."""

    async def dependency(ctx: WorkspaceContext = Depends(get_workspace_context)) -> WorkspaceContext:
        if not has_permission(ctx.membership.role, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role cannot perform this action",
            )
        return ctx

    return dependency


def require_permission_scope(scope: str, action: str):
    """Allow the request when an API key holds ``scope`` **or** a console user's
    role grants ``action`` (so a read-only role cannot write via the console)."""

    async def dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if ctx.actor_type == "user":
            role = ctx.membership.role if ctx.membership else None
            if not has_permission(role, action):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your role cannot perform this action",
                )
        elif scope not in ctx.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing scope(s): {scope}",
            )
        return ctx

    return dependency


# --- Integration (API key) ----------------------------------------------------


@dataclass
class IntegrationContext:
    workspace: Workspace
    integration: Integration
    api_key: ApiKey
    scopes: set[str]


async def _resolve_api_key(db: AsyncSession, raw: str) -> tuple[Integration, Workspace, ApiKey]:
    key = (
        await db.execute(
            select(ApiKey).where(
                ApiKey.secret_hash == hash_api_key(raw),
                ApiKey.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    integration = (
        await db.execute(select(Integration).where(Integration.id == key.integration_id))
    ).scalar_one_or_none()
    if integration is None or not integration.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Integration is disabled")
    workspace = (
        await db.execute(select(Workspace).where(Workspace.id == integration.workspace_id))
    ).scalar_one_or_none()
    if workspace is None or not workspace.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace is inactive")
    key.last_used_at = utcnow()
    await db.commit()
    return integration, workspace, key


async def get_integration_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    db: AsyncSession = Depends(get_db),
) -> IntegrationContext:
    """Resolve an integration from its API key (Bearer or ``X-Api-Key``)."""
    raw = x_api_key or (credentials.credentials if credentials is not None else None)
    if not raw:
        raise _UNAUTHORIZED
    integration, workspace, key = await _resolve_api_key(db, raw)
    return IntegrationContext(
        workspace=workspace,
        integration=integration,
        api_key=key,
        scopes=set(key.scopes or []),
    )


def require_scopes(*required: str):
    """Allow the request only when the integration key grants *all* of ``required``."""

    async def dependency(ctx: IntegrationContext = Depends(get_integration_context)) -> IntegrationContext:
        missing = [scope for scope in required if scope not in ctx.scopes]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key is missing scope(s): {', '.join(missing)}",
            )
        return ctx

    return dependency


# --- Either credential (tickets and other shared resources) -------------------


@dataclass
class TenantContext:
    workspace: Workspace
    scopes: set[str]
    actor_type: str  # "user" | "integration"
    integration: Integration | None = None
    user: User | None = None
    membership: Membership | None = None


async def get_tenant_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    workspace_id: UUID | None = Header(default=None, alias="X-Workspace-ID"),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """Accept either an API key or a console JWT and return a tenant context.

    An API key is used when ``X-Api-Key`` is present or the bearer token carries
    the key prefix; otherwise the bearer is treated as a console JWT.
    """
    raw = x_api_key or (credentials.credentials if credentials is not None else None)
    if not raw:
        raise _UNAUTHORIZED
    if x_api_key is not None or raw.startswith(f"{settings.api_key_prefix}_"):
        integration, workspace, key = await _resolve_api_key(db, raw)
        return TenantContext(
            workspace=workspace,
            scopes=set(key.scopes or []),
            actor_type="integration",
            integration=integration,
        )
    user = await _load_user_from_token(db, raw)
    membership, workspace = await _resolve_workspace(db, user, workspace_id)
    return TenantContext(
        workspace=workspace,
        scopes=set(CONSOLE_SCOPES),
        actor_type="user",
        user=user,
        membership=membership,
    )


def require_tenant_scopes(*required: str):
    """Allow the request only when the tenant grants *all* of ``required``."""

    async def dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        missing = [scope for scope in required if scope not in ctx.scopes]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing scope(s): {', '.join(missing)}",
            )
        return ctx

    return dependency


# --- Requester (portal token) -------------------------------------------------


@dataclass
class RequesterContext:
    workspace: Workspace
    requester: Requester


async def get_requester_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_requester_token: str | None = Header(default=None, alias="X-Requester-Token"),
    db: AsyncSession = Depends(get_db),
) -> RequesterContext:
    """Resolve an external requester from a portal token (Bearer or header).

    The token is looked up by its SHA-256 digest, so the plaintext is never
    stored. A requester only ever reaches its own workspace and tickets.
    """
    raw = x_requester_token or (credentials.credentials if credentials is not None else None)
    if not raw:
        raise _UNAUTHORIZED
    requester = (
        await db.execute(select(Requester).where(Requester.portal_token_hash == hash_api_key(raw)))
    ).scalar_one_or_none()
    if requester is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid requester token")
    workspace = (
        await db.execute(select(Workspace).where(Workspace.id == requester.workspace_id))
    ).scalar_one_or_none()
    if workspace is None or not workspace.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace is inactive")
    return RequesterContext(workspace=workspace, requester=requester)


# --- Platform operator --------------------------------------------------------


async def get_platform_admin(user: User = Depends(get_current_user)) -> User:
    if user.platform_role not in {"admin", "super_admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin access required")
    return user
