"""Audit log (v1). Scope: ``tickets:read``."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.schemas import AuditListRead
from app.services import audit as svc

router = APIRouter(prefix="/audit", tags=["audit"])

_read = require_tenant_scopes("tickets:read")


@router.get("", response_model=AuditListRead)
async def list_events(
    type: str | None = None,
    actor_type: str | None = None,
    ticket_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> AuditListRead:
    return await svc.list_events(
        db,
        ctx.workspace.id,
        type=type,
        actor_type=actor_type,
        ticket_id=ticket_id,
        limit=limit,
        cursor=cursor,
    )
