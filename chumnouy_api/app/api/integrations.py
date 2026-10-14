"""Integrations and their API keys (console, owner/admin only).

An integration is a registered client app inside the workspace. Its keys carry
the scopes a machine client may use; the plaintext key is returned exactly once.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import WorkspaceContext, require_workspace_roles
from app.models import ApiKey, Integration, utcnow
from app.schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyRead, IntegrationCreate, IntegrationRead
from app.scopes import normalise_scopes
from app.security import api_key_prefix, generate_api_key, hash_api_key, slugify

router = APIRouter(prefix="/integrations", tags=["integrations"])

_owner = require_workspace_roles("owner", "admin")


async def _unique_integration_slug(db: AsyncSession, workspace_id, base: str) -> str:
    slug = slugify(base)
    candidate = slug
    suffix = 1
    while (
        await db.execute(
            select(Integration.id).where(
                Integration.workspace_id == workspace_id, Integration.slug == candidate
            )
        )
    ).scalar_one_or_none() is not None:
        suffix += 1
        candidate = f"{slug}-{suffix}"
    return candidate


async def _load_integration(db: AsyncSession, ctx: WorkspaceContext, integration_id: UUID) -> Integration:
    integration = (
        await db.execute(
            select(Integration).where(
                Integration.id == integration_id,
                Integration.workspace_id == ctx.workspace.id,
            )
        )
    ).scalar_one_or_none()
    if integration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return integration


@router.post("", response_model=IntegrationRead, status_code=status.HTTP_201_CREATED)
async def create_integration(
    payload: IntegrationCreate,
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> IntegrationRead:
    integration = Integration(
        workspace_id=ctx.workspace.id,
        name=payload.name.strip(),
        slug=await _unique_integration_slug(db, ctx.workspace.id, payload.name),
        scopes=normalise_scopes(payload.scopes),
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)
    return IntegrationRead.model_validate(integration)


@router.get("", response_model=list[IntegrationRead])
async def list_integrations(
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> list[IntegrationRead]:
    rows = (
        await db.execute(
            select(Integration)
            .where(Integration.workspace_id == ctx.workspace.id)
            .order_by(Integration.created_at)
        )
    ).scalars().all()
    return [IntegrationRead.model_validate(row) for row in rows]


@router.post(
    "/{integration_id}/keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_key(
    integration_id: UUID,
    payload: ApiKeyCreate,
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreated:
    integration = await _load_integration(db, ctx, integration_id)
    raw = generate_api_key(payload.environment)
    key = ApiKey(
        integration_id=integration.id,
        name=payload.name.strip(),
        key_prefix=api_key_prefix(raw),
        secret_hash=hash_api_key(raw),
        environment=payload.environment,
        scopes=normalise_scopes(payload.scopes or integration.scopes),
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return ApiKeyCreated(key=raw, api_key=ApiKeyRead.model_validate(key))


@router.get("/{integration_id}/keys", response_model=list[ApiKeyRead])
async def list_keys(
    integration_id: UUID,
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> list[ApiKeyRead]:
    integration = await _load_integration(db, ctx, integration_id)
    rows = (
        await db.execute(
            select(ApiKey)
            .where(ApiKey.integration_id == integration.id)
            .order_by(ApiKey.created_at)
        )
    ).scalars().all()
    return [ApiKeyRead.model_validate(row) for row in rows]


@router.post("/keys/{key_id}/revoke", response_model=ApiKeyRead)
async def revoke_key(
    key_id: UUID,
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyRead:
    key = (
        await db.execute(
            select(ApiKey)
            .join(Integration, Integration.id == ApiKey.integration_id)
            .where(ApiKey.id == key_id, Integration.workspace_id == ctx.workspace.id)
        )
    ).scalar_one_or_none()
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    if key.revoked_at is None:
        key.revoked_at = utcnow()
        await db.commit()
        await db.refresh(key)
    return ApiKeyRead.model_validate(key)
