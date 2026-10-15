"""Workspace-scoped search (v1). Scope: ``tickets:read``."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.schemas import SearchResults
from app.services import search as svc

router = APIRouter(prefix="/search", tags=["search"])

_read = require_tenant_scopes("tickets:read")


@router.get("", response_model=SearchResults)
async def search(
    q: str = Query(min_length=1),
    types: str | None = Query(default=None, description="Comma-separated: ticket,message,article"),
    limit: int = 30,
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> SearchResults:
    wanted = [t.strip() for t in types.split(",")] if types else None
    return await svc.search(db, ctx.workspace.id, q=q, types=wanted, limit=limit)
