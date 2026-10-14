"""Authentication and workspace resolution.

Three credentials resolve to a workspace context (docs/tenancy.md):

* **User JWT** (console) → :func:`get_current_user` / :func:`get_workspace_context`
* **API key** (machine)  → :func:`get_integration_context`

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

from app.db import get_db
from app.models import ApiKey, Integration, Membership, User, Workspace, utcnow
from app.security import decode_token, hash_api_key

bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


# --- Console (user JWT) -------------------------------------------------------


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise _UNAUTHORIZED
    try:
        payload = decode_token(credentials.credentials)
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
    """Resolve the active workspace for a signed-in user.

    Honours an explicit ``X-Workspace-ID`` choice, then falls back
    deterministically: the only membership, or an owner one. Refuses to guess
    when the user belongs to several workspaces with no choice made.
    """
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
                return WorkspaceContext(user=user, workspace=workspace, membership=membership)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    if len(rows) == 1:
        membership, workspace = rows[0]
        return WorkspaceContext(user=user, workspace=workspace, membership=membership)
    owners = [(m, w) for m, w in rows if m.role == "owner"]
    if owners:
        membership, workspace = owners[0]
        return WorkspaceContext(user=user, workspace=workspace, membership=membership)
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="You belong to more than one workspace. Choose one with the X-Workspace-ID header",
    )


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


# --- Integration (API key) ----------------------------------------------------


@dataclass
class IntegrationContext:
    workspace: Workspace
    integration: Integration
    api_key: ApiKey
    scopes: set[str]


async def get_integration_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    db: AsyncSession = Depends(get_db),
) -> IntegrationContext:
    """Resolve an integration from its API key (Bearer or ``X-Api-Key``)."""
    raw = x_api_key or (credentials.credentials if credentials is not None else None)
    if not raw:
        raise _UNAUTHORIZED
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


# --- Platform operator --------------------------------------------------------


async def get_platform_admin(user: User = Depends(get_current_user)) -> User:
    if user.platform_role not in {"admin", "super_admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin access required")
    return user
