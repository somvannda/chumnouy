"""Ticket endpoints (v1). Accept either a console JWT or an integration API key.

Scopes: ``tickets:read`` for reads, ``tickets:write`` for writes. A console user
carries all scopes; an API key is limited to the scopes it was created with.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.models import Ticket, TicketEvent
from app.schemas import (
    AttachmentClaim,
    AttachmentRead,
    TicketCreate,
    TicketDetailRead,
    TicketListRead,
    TicketMessageCreate,
    TicketMessageRead,
    TicketRead,
    TicketUpdate,
)
from app.services import attachments as attachments_svc
from app.services import idempotency as idempotency_svc
from app.services import quota as quota_svc
from app.services import tickets as svc

router = APIRouter(prefix="/tickets", tags=["tickets"])

_read = require_tenant_scopes("tickets:read")
_write = require_tenant_scopes("tickets:write")


async def _get_ticket(db: AsyncSession, ctx: TenantContext, ticket_id: UUID) -> Ticket:
    ticket = await svc.load_ticket(db, ctx.workspace.id, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.post("", response_model=TicketDetailRead, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> TicketDetailRead:
    # A retry with the same key returns the original response, not a new ticket.
    if idempotency_key:
        stored = await idempotency_svc.get_stored(db, ctx.workspace.id, idempotency_key)
        if stored is not None:
            return JSONResponse(content=stored.response, status_code=stored.status_code)
    await quota_svc.enforce_ticket_quota(db, ctx.workspace)
    try:
        result = await svc.create_ticket(db, ctx, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if idempotency_key:
        await idempotency_svc.store(
            db,
            workspace_id=ctx.workspace.id,
            key=idempotency_key,
            endpoint="tickets.create",
            status_code=status.HTTP_201_CREATED,
            response=result.model_dump(mode="json"),
        )
    return result


@router.get("", response_model=TicketListRead)
async def list_tickets(
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    assignee: str | None = None,
    integration: UUID | None = None,
    q: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> TicketListRead:
    return await svc.list_tickets(
        db,
        ctx.workspace.id,
        status=status_filter,
        priority=priority,
        assignee=assignee,
        integration_id=integration,
        q=q,
        limit=limit,
        cursor=cursor,
    )


@router.get("/{ticket_id}", response_model=TicketDetailRead)
async def get_ticket(
    ticket_id: UUID,
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> TicketDetailRead:
    ticket = await _get_ticket(db, ctx, ticket_id)
    return await svc.ticket_detail(db, ticket)


@router.patch("/{ticket_id}", response_model=TicketRead)
async def update_ticket(
    ticket_id: UUID,
    payload: TicketUpdate,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> TicketRead:
    ticket = await _get_ticket(db, ctx, ticket_id)
    return await svc.apply_update(db, ctx, ticket, payload)


@router.post("/{ticket_id}/messages", response_model=TicketMessageRead, status_code=status.HTTP_201_CREATED)
async def add_message(
    ticket_id: UUID,
    payload: TicketMessageCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> TicketMessageRead:
    ticket = await _get_ticket(db, ctx, ticket_id)
    if idempotency_key:
        stored = await idempotency_svc.get_stored(db, ctx.workspace.id, idempotency_key)
        if stored is not None:
            return JSONResponse(content=stored.response, status_code=stored.status_code)
    try:
        result = await svc.add_message(db, ctx, ticket, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if idempotency_key:
        await idempotency_svc.store(
            db,
            workspace_id=ctx.workspace.id,
            key=idempotency_key,
            endpoint="tickets.reply",
            status_code=status.HTTP_201_CREATED,
            response=result.model_dump(mode="json"),
        )
    return result


@router.post(
    "/{ticket_id}/attachments",
    response_model=list[AttachmentRead],
    status_code=status.HTTP_201_CREATED,
)
async def attach_files(
    ticket_id: UUID,
    payload: AttachmentClaim,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> list[AttachmentRead]:
    """Claim staged uploads onto a ticket (no message) as opening files."""
    ticket = await _get_ticket(db, ctx, ticket_id)
    try:
        return await attachments_svc.claim_attachments(db, ctx, ticket, payload.attachment_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{ticket_id}/resolve", response_model=TicketRead)
async def resolve_ticket(
    ticket_id: UUID,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> TicketRead:
    ticket = await _get_ticket(db, ctx, ticket_id)
    return await svc.set_status(db, ctx, ticket, "resolved", event="ticket.resolved")


@router.post("/{ticket_id}/reopen", response_model=TicketRead)
async def reopen_ticket(
    ticket_id: UUID,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> TicketRead:
    ticket = await _get_ticket(db, ctx, ticket_id)
    return await svc.set_status(db, ctx, ticket, "open", event="ticket.reopened")


@router.get("/{ticket_id}/events")
async def ticket_events(
    ticket_id: UUID,
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    await _get_ticket(db, ctx, ticket_id)
    rows = (
        await db.execute(
            select(TicketEvent)
            .where(TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.created_at)
        )
    ).scalars().all()
    return [
        {
            "id": str(row.id),
            "type": row.type,
            "actor_type": row.actor_type,
            "actor_id": str(row.actor_id) if row.actor_id else None,
            "data": row.data or {},
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
