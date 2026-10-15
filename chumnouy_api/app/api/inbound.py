"""Inbound email webhook (called by Notifyr). Scope: ``tickets:write``."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.schemas import InboundEmailCreate, TicketDetailRead
from app.services import inbound as svc

router = APIRouter(prefix="/inbound", tags=["inbound"])

_write = require_tenant_scopes("tickets:write")


@router.post("/email", response_model=TicketDetailRead, status_code=status.HTTP_201_CREATED)
async def inbound_email(
    payload: InboundEmailCreate,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> TicketDetailRead:
    """Create or append a ticket from a parsed inbound email.

    The transport and parsing live in Notifyr; this endpoint is the hand-off.
    ``in_reply_to`` threads the message onto the matching ticket.
    """
    return await svc.handle_inbound_email(db, ctx.workspace, payload)
