"""Reporting (v1). Scope: ``tickets:read``."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.schemas import ReportSummary
from app.services import reports as svc

router = APIRouter(prefix="/reports", tags=["reports"])

_read = require_tenant_scopes("tickets:read")


@router.get("/summary", response_model=ReportSummary)
async def summary(
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> ReportSummary:
    return await svc.summary(db, ctx.workspace.id)
