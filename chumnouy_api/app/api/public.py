"""Public (requester-token) surface (v1).

A requester authenticates with a portal token (``X-Requester-Token`` or Bearer)
and only ever sees their own tickets: reads return public messages only, hiding
internal notes.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import RequesterContext, get_requester_context
from app.schemas import (
    CsatRead,
    CsatSubmit,
    PublicTicketCreate,
    PublicTicketMessageCreate,
    TicketDetailRead,
    TicketListRead,
    TicketMessageRead,
)
from app.services import csat as csat_svc
from app.services import public as svc
from app.services import quota as quota_svc

router = APIRouter(prefix="/public", tags=["public"])

_requester = get_requester_context


async def _ticket(db: AsyncSession, ctx: RequesterContext, ticket_id: UUID):
    ticket = await svc.load_portal_ticket(db, ctx.workspace.id, ctx.requester.id, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.get("/tickets", response_model=TicketListRead)
async def list_my_tickets(
    limit: int = 50,
    ctx: RequesterContext = Depends(_requester),
    db: AsyncSession = Depends(get_db),
) -> TicketListRead:
    return await svc.list_portal_tickets(db, ctx.workspace.id, ctx.requester, limit=limit)


@router.post("/tickets", response_model=TicketDetailRead, status_code=status.HTTP_201_CREATED)
async def create_my_ticket(
    payload: PublicTicketCreate,
    ctx: RequesterContext = Depends(_requester),
    db: AsyncSession = Depends(get_db),
) -> TicketDetailRead:
    await quota_svc.enforce_ticket_quota(db, ctx.workspace)
    try:
        return await svc.create_portal_ticket(db, ctx.workspace, ctx.requester, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/tickets/{ticket_id}", response_model=TicketDetailRead)
async def get_my_ticket(
    ticket_id: UUID,
    ctx: RequesterContext = Depends(_requester),
    db: AsyncSession = Depends(get_db),
) -> TicketDetailRead:
    ticket = await _ticket(db, ctx, ticket_id)
    return await svc.portal_ticket_detail(db, ctx.requester, ticket)


@router.post(
    "/tickets/{ticket_id}/messages",
    response_model=TicketMessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def reply_my_ticket(
    ticket_id: UUID,
    payload: PublicTicketMessageCreate,
    ctx: RequesterContext = Depends(_requester),
    db: AsyncSession = Depends(get_db),
) -> TicketMessageRead:
    ticket = await _ticket(db, ctx, ticket_id)
    try:
        return await svc.add_portal_message(db, ctx.workspace, ctx.requester, ticket, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/tickets/{ticket_id}/csat", response_model=CsatRead, status_code=status.HTTP_201_CREATED)
async def submit_csat(
    ticket_id: UUID,
    payload: CsatSubmit,
    ctx: RequesterContext = Depends(_requester),
    db: AsyncSession = Depends(get_db),
) -> CsatRead:
    ticket = await _ticket(db, ctx, ticket_id)
    return await csat_svc.submit(db, ctx.workspace, ticket, payload)
