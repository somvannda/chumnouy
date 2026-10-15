"""Triggers (event-based rules). Scopes: tickets:read / tickets:write."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.schemas import TriggerCreate, TriggerRead, TriggerUpdate
from app.services import triggers as svc

router = APIRouter(prefix="/triggers", tags=["triggers"])

_read = require_tenant_scopes("tickets:read")
_write = require_tenant_scopes("tickets:write")


async def _load(db: AsyncSession, ctx: TenantContext, trigger_id: UUID):
    row = await svc.load_trigger(db, ctx.workspace.id, trigger_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trigger not found")
    return row


@router.get("", response_model=list[TriggerRead])
async def list_triggers(
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[TriggerRead]:
    return await svc.list_triggers(db, ctx.workspace.id)


@router.post("", response_model=TriggerRead, status_code=status.HTTP_201_CREATED)
async def create_trigger(
    payload: TriggerCreate,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> TriggerRead:
    return await svc.create_trigger(db, ctx.workspace.id, payload)


@router.get("/{trigger_id}", response_model=TriggerRead)
async def get_trigger(
    trigger_id: UUID,
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> TriggerRead:
    return svc.trigger_read(await _load(db, ctx, trigger_id))


@router.patch("/{trigger_id}", response_model=TriggerRead)
async def update_trigger(
    trigger_id: UUID,
    payload: TriggerUpdate,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> TriggerRead:
    return await svc.update_trigger(db, await _load(db, ctx, trigger_id), payload)


@router.delete("/{trigger_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trigger(
    trigger_id: UUID,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> None:
    await svc.delete_trigger(db, await _load(db, ctx, trigger_id))
