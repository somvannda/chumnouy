"""Time-based automations. Scopes: tickets:read / tickets:write."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.schemas import AutomationCreate, AutomationRead, AutomationUpdate
from app.services import automations as svc

router = APIRouter(prefix="/automations", tags=["automations"])

_read = require_tenant_scopes("tickets:read")
_write = require_tenant_scopes("tickets:write")


async def _load(db: AsyncSession, ctx: TenantContext, automation_id: UUID):
    row = await svc.load_automation(db, ctx.workspace.id, automation_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
    return row


@router.get("", response_model=list[AutomationRead])
async def list_automations(
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[AutomationRead]:
    return await svc.list_automations(db, ctx.workspace.id)


@router.post("", response_model=AutomationRead, status_code=status.HTTP_201_CREATED)
async def create_automation(
    payload: AutomationCreate,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> AutomationRead:
    return await svc.create_automation(db, ctx.workspace.id, payload)


@router.get("/{automation_id}", response_model=AutomationRead)
async def get_automation(
    automation_id: UUID,
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> AutomationRead:
    return svc.automation_read(await _load(db, ctx, automation_id))


@router.patch("/{automation_id}", response_model=AutomationRead)
async def update_automation(
    automation_id: UUID,
    payload: AutomationUpdate,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> AutomationRead:
    return await svc.update_automation(db, await _load(db, ctx, automation_id), payload)


@router.delete("/{automation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_automation(
    automation_id: UUID,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> None:
    await svc.delete_automation(db, await _load(db, ctx, automation_id))
