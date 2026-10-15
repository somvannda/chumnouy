"""Bulk ticket actions (console). Scope: ``tickets:write``."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.schemas import BulkResult, BulkUpdate
from app.services import bulk as svc

router = APIRouter(prefix="/console", tags=["console"])

_write = require_tenant_scopes("tickets:write")


@router.post("/bulk", response_model=BulkResult)
async def bulk_update(
    payload: BulkUpdate,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> BulkResult:
    """Apply one action (status/priority/assignee/team/tags) to many tickets."""
    return await svc.apply_bulk(db, ctx, payload)
