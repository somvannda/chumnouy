"""Requester management (v1). Scopes: ``requesters:read`` / ``requesters:write``."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.schemas import RequesterDetail, RequesterPortalToken, RequesterRead, RequesterUpdate
from app.services import requesters as svc

router = APIRouter(prefix="/requesters", tags=["requesters"])

_read = require_tenant_scopes("requesters:read")
_write = require_tenant_scopes("requesters:write")


async def _get_requester(db: AsyncSession, ctx: TenantContext, requester_id: UUID):
    requester = await svc.load_requester(db, ctx.workspace.id, requester_id)
    if requester is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requester not found")
    return requester


@router.get("", response_model=list[RequesterRead])
async def list_requesters(
    q: str | None = None,
    limit: int = 50,
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[RequesterRead]:
    return await svc.list_requesters(db, ctx.workspace.id, q=q, limit=limit)


@router.get("/{requester_id}", response_model=RequesterDetail)
async def get_requester(
    requester_id: UUID,
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> RequesterDetail:
    requester = await _get_requester(db, ctx, requester_id)
    return await svc.requester_detail(db, ctx.workspace.id, requester)


@router.patch("/{requester_id}", response_model=RequesterRead)
async def update_requester(
    requester_id: UUID,
    payload: RequesterUpdate,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> RequesterRead:
    requester = await _get_requester(db, ctx, requester_id)
    return await svc.update_requester(db, requester, payload)


@router.post(
    "/{requester_id}/portal-token",
    response_model=RequesterPortalToken,
    status_code=status.HTTP_201_CREATED,
)
async def issue_portal_token(
    requester_id: UUID,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> RequesterPortalToken:
    """Issue (or rotate) the requester's public-surface token; shown once."""
    requester = await _get_requester(db, ctx, requester_id)
    token, prefix = await svc.issue_portal_token(db, requester)
    return RequesterPortalToken(token=token, token_prefix=prefix)
