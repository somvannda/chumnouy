"""Canned responses: workspace-scoped saved replies."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import TenantContext
from app.models import CannedResponse
from app.schemas import CannedResponseCreate, CannedResponseRead, CannedResponseUpdate
from app.services.sanitize import render_body


def _read(row: CannedResponse) -> CannedResponseRead:
    return CannedResponseRead(
        id=row.id,
        title=row.title,
        body=row.body,
        body_format=row.body_format,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_canned(db: AsyncSession, workspace_id: UUID) -> list[CannedResponseRead]:
    rows = (
        await db.execute(
            select(CannedResponse)
            .where(CannedResponse.workspace_id == workspace_id)
            .order_by(CannedResponse.title)
        )
    ).scalars().all()
    return [_read(row) for row in rows]


async def load_canned(
    db: AsyncSession, workspace_id: UUID, canned_id: UUID
) -> CannedResponse | None:
    return (
        await db.execute(
            select(CannedResponse).where(
                CannedResponse.id == canned_id, CannedResponse.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()


async def create_canned(
    db: AsyncSession, ctx: TenantContext, payload: CannedResponseCreate
) -> CannedResponseRead:
    row = CannedResponse(
        workspace_id=ctx.workspace.id,
        title=payload.title.strip(),
        body=render_body(payload.body, payload.body_format),
        body_format=payload.body_format,
        created_by=ctx.user.id if ctx.user else None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _read(row)


async def update_canned(
    db: AsyncSession, row: CannedResponse, payload: CannedResponseUpdate
) -> CannedResponseRead:
    if payload.title is not None:
        row.title = payload.title.strip()
    if payload.body is not None:
        row.body = render_body(payload.body, payload.body_format or row.body_format)
    if payload.body_format is not None:
        row.body_format = payload.body_format
    await db.commit()
    await db.refresh(row)
    return _read(row)


async def delete_canned(db: AsyncSession, row: CannedResponse) -> None:
    await db.delete(row)
    await db.commit()
