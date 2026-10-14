"""Requester management and portal tokens.

A requester is the integrator's external end user. A portal token is an opaque
credential the integrator hands to that end user so they can use the public
surface (``/v1/public/tickets``) without a console account; only its SHA-256
digest is stored (see ``hash_api_key``). All functions are workspace-scoped.
"""
from __future__ import annotations

import secrets
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Requester, Ticket, utcnow
from app.schemas import RequesterDetail, RequesterRead, RequesterUpdate
from app.security import hash_api_key
from app.services.tickets import ticket_read

PORTAL_TOKEN_PREFIX = "rqt"


def requester_read(requester: Requester) -> RequesterRead:
    return RequesterRead(
        id=requester.id,
        external_id=requester.external_id,
        name=requester.name,
        email=requester.email,
        phone=requester.phone,
        metadata=requester.metadata_json or {},
    )


def generate_portal_token() -> str:
    return f"{PORTAL_TOKEN_PREFIX}_{secrets.token_urlsafe(32)}"


def token_prefix(token: str, length: int = 12) -> str:
    return token[:length]


async def list_requesters(
    db: AsyncSession,
    workspace_id: UUID,
    *,
    q: str | None = None,
    limit: int = 50,
) -> list[RequesterRead]:
    stmt = select(Requester).where(Requester.workspace_id == workspace_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Requester.external_id.ilike(like),
                Requester.name.ilike(like),
                Requester.email.ilike(like),
            )
        )
    stmt = stmt.order_by(Requester.created_at.desc()).limit(max(1, min(limit, 200)))
    rows = (await db.execute(stmt)).scalars().all()
    return [requester_read(requester) for requester in rows]


async def load_requester(
    db: AsyncSession, workspace_id: UUID, requester_id: UUID
) -> Requester | None:
    return (
        await db.execute(
            select(Requester).where(
                Requester.id == requester_id, Requester.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()


async def requester_detail(
    db: AsyncSession, workspace_id: UUID, requester: Requester
) -> RequesterDetail:
    tickets = (
        await db.execute(
            select(Ticket)
            .where(Ticket.workspace_id == workspace_id, Ticket.requester_id == requester.id)
            .order_by(Ticket.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    base = requester_read(requester)
    return RequesterDetail(
        **base.model_dump(),
        tickets=[ticket_read(ticket, requester) for ticket in tickets],
    )


async def update_requester(
    db: AsyncSession, requester: Requester, payload: RequesterUpdate
) -> RequesterRead:
    if payload.name is not None:
        requester.name = payload.name
    if payload.email is not None:
        requester.email = payload.email
    if payload.phone is not None:
        requester.phone = payload.phone
    if payload.metadata is not None:
        merged = dict(requester.metadata_json or {})
        merged.update(payload.metadata)
        requester.metadata_json = merged
    await db.commit()
    await db.refresh(requester)
    return requester_read(requester)


async def issue_portal_token(db: AsyncSession, requester: Requester) -> tuple[str, str]:
    """Issue (or rotate) a requester's portal token. Returns ``(token, prefix)``."""
    token = generate_portal_token()
    requester.portal_token_hash = hash_api_key(token)
    requester.portal_token_prefix = token_prefix(token)
    requester.portal_token_issued_at = utcnow()
    await db.commit()
    await db.refresh(requester)
    return token, requester.portal_token_prefix or ""
