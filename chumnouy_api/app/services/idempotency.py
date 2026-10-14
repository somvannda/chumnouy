"""Idempotent writes.

A client sends ``Idempotency-Key: <uuid>`` on a write; the first response is
stored per workspace and replayed verbatim on a repeat, so a network retry never
creates a second ticket. Keys are checked-then-stored with a unique constraint as
the backstop (docs/api.md conventions).
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IdempotencyKey


async def get_stored(db: AsyncSession, workspace_id: UUID, key: str) -> IdempotencyKey | None:
    return (
        await db.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.workspace_id == workspace_id,
                IdempotencyKey.key == key,
            )
        )
    ).scalar_one_or_none()


async def store(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    key: str,
    endpoint: str,
    status_code: int,
    response: dict,
) -> IdempotencyKey:
    record = IdempotencyKey(
        workspace_id=workspace_id,
        key=key,
        endpoint=endpoint,
        status_code=status_code,
        response=response,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record
