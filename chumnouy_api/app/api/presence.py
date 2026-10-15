"""Ticket presence (console). Heartbeat + who is viewing."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import WorkspaceContext, get_workspace_context
from app.schemas import PresenceRead
from app.services import presence as svc
from app.services import tickets as tickets_svc

router = APIRouter(tags=["presence"])


async def _assert_ticket(db: AsyncSession, ctx: WorkspaceContext, ticket_id: UUID) -> None:
    if await tickets_svc.load_ticket(db, ctx.workspace.id, ticket_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")


@router.post("/tickets/{ticket_id}/presence", response_model=PresenceRead)
async def heartbeat(
    ticket_id: UUID,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> PresenceRead:
    await _assert_ticket(db, ctx, ticket_id)
    await svc.heartbeat(db, ticket_id, ctx.user.id)
    return PresenceRead(viewers=await svc.viewers(db, ticket_id))


@router.get("/tickets/{ticket_id}/presence", response_model=PresenceRead)
async def get_presence(
    ticket_id: UUID,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> PresenceRead:
    await _assert_ticket(db, ctx, ticket_id)
    return PresenceRead(viewers=await svc.viewers(db, ticket_id))
