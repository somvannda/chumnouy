"""Macros: CRUD + apply-on-demand. Scopes: tickets:read / tickets:write."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.schemas import MacroCreate, MacroRead, MacroUpdate, TicketRead
from app.services import macros as svc
from app.services import tickets as tickets_svc

router = APIRouter(tags=["macros"])

_read = require_tenant_scopes("tickets:read")
_write = require_tenant_scopes("tickets:write")


async def _load(db: AsyncSession, ctx: TenantContext, macro_id: UUID):
    macro = await svc.load_macro(db, ctx.workspace.id, macro_id)
    if macro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Macro not found")
    return macro


@router.get("/macros", response_model=list[MacroRead])
async def list_macros(
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[MacroRead]:
    return await svc.list_macros(db, ctx.workspace.id)


@router.post("/macros", response_model=MacroRead, status_code=status.HTTP_201_CREATED)
async def create_macro(
    payload: MacroCreate,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> MacroRead:
    return await svc.create_macro(db, ctx.workspace.id, payload)


@router.get("/macros/{macro_id}", response_model=MacroRead)
async def get_macro(
    macro_id: UUID,
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> MacroRead:
    return svc.macro_read(await _load(db, ctx, macro_id))


@router.patch("/macros/{macro_id}", response_model=MacroRead)
async def update_macro(
    macro_id: UUID,
    payload: MacroUpdate,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> MacroRead:
    return await svc.update_macro(db, await _load(db, ctx, macro_id), payload)


@router.delete("/macros/{macro_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_macro(
    macro_id: UUID,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> None:
    await svc.delete_macro(db, await _load(db, ctx, macro_id))


@router.post("/tickets/{ticket_id}/macros/{macro_id}", response_model=TicketRead)
async def apply_macro(
    ticket_id: UUID,
    macro_id: UUID,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> TicketRead:
    ticket = await tickets_svc.load_ticket(db, ctx.workspace.id, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return await svc.apply_macro(db, ctx, ticket, await _load(db, ctx, macro_id))
