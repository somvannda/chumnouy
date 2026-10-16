"""Reporting (v1). Scope: ``tickets:read``."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.schemas import ReportDaily, ReportSummary
from app.services import reports as svc

router = APIRouter(prefix="/reports", tags=["reports"])

_read = require_tenant_scopes("tickets:read")


@router.get("/summary", response_model=ReportSummary)
async def summary(
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> ReportSummary:
    return await svc.summary(db, ctx.workspace.id)


@router.get("/daily", response_model=ReportDaily)
async def daily(
    days: int = 14,
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> ReportDaily:
    """Per-day activity for the last ``days`` days (1–90, dense window)."""
    return await svc.daily(db, ctx.workspace.id, days=days)
