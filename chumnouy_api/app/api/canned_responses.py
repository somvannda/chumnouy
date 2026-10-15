"""Canned responses (saved replies). Scopes: tickets:read / tickets:write."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.schemas import CannedResponseCreate, CannedResponseRead, CannedResponseUpdate
from app.services import canned_responses as svc

router = APIRouter(prefix="/canned-responses", tags=["canned-responses"])

_read = require_tenant_scopes("tickets:read")
_write = require_tenant_scopes("tickets:write")


async def _load(db: AsyncSession, ctx: TenantContext, canned_id: UUID):
    row = await svc.load_canned(db, ctx.workspace.id, canned_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Canned response not found")
    return row


@router.get("", response_model=list[CannedResponseRead])
async def list_canned(
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[CannedResponseRead]:
    return await svc.list_canned(db, ctx.workspace.id)


@router.post("", response_model=CannedResponseRead, status_code=status.HTTP_201_CREATED)
async def create_canned(
    payload: CannedResponseCreate,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> CannedResponseRead:
    return await svc.create_canned(db, ctx, payload)


@router.get("/{canned_id}", response_model=CannedResponseRead)
async def get_canned(
    canned_id: UUID,
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> CannedResponseRead:
    return svc._read(await _load(db, ctx, canned_id))


@router.patch("/{canned_id}", response_model=CannedResponseRead)
async def update_canned(
    canned_id: UUID,
    payload: CannedResponseUpdate,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> CannedResponseRead:
    return await svc.update_canned(db, await _load(db, ctx, canned_id), payload)


@router.delete("/{canned_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_canned(
    canned_id: UUID,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> None:
    await svc.delete_canned(db, await _load(db, ctx, canned_id))
