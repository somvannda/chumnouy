"""Webhook registrations and their delivery log (v1).

Machine + console, gated by the ``webhooks:manage`` scope. A webhook's signing
secret is returned once at creation and never again by a read endpoint.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.models import Webhook, WebhookDelivery
from app.schemas import (
    WebhookCreate,
    WebhookCreated,
    WebhookDeliveryRead,
    WebhookRead,
    WebhookUpdate,
)
from app.services import webhooks as svc

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_manage = require_tenant_scopes("webhooks:manage")


async def _load(db: AsyncSession, ctx: TenantContext, webhook_id: UUID) -> Webhook:
    hook = (
        await db.execute(
            select(Webhook).where(
                Webhook.id == webhook_id, Webhook.workspace_id == ctx.workspace.id
            )
        )
    ).scalar_one_or_none()
    if hook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return hook


@router.post("", response_model=WebhookCreated, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    payload: WebhookCreate,
    ctx: TenantContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> WebhookCreated:
    secret = svc.generate_secret()
    hook = Webhook(
        workspace_id=ctx.workspace.id,
        url=payload.url.strip(),
        description=payload.description,
        secret=secret,
        events=svc.normalise_events(payload.events),
        is_active=payload.is_active,
        created_by=ctx.user.id if ctx.user else None,
    )
    db.add(hook)
    await db.commit()
    await db.refresh(hook)
    return WebhookCreated(secret=secret, webhook=svc.webhook_read(hook))


@router.get("", response_model=list[WebhookRead])
async def list_webhooks(
    ctx: TenantContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookRead]:
    rows = (
        await db.execute(
            select(Webhook)
            .where(Webhook.workspace_id == ctx.workspace.id)
            .order_by(Webhook.created_at)
        )
    ).scalars().all()
    return [svc.webhook_read(hook) for hook in rows]


@router.patch("/{webhook_id}", response_model=WebhookRead)
async def update_webhook(
    webhook_id: UUID,
    payload: WebhookUpdate,
    ctx: TenantContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> WebhookRead:
    hook = await _load(db, ctx, webhook_id)
    if payload.url is not None:
        hook.url = payload.url.strip()
    if payload.description is not None:
        hook.description = payload.description
    if payload.events is not None:
        hook.events = svc.normalise_events(payload.events)
    if payload.is_active is not None:
        hook.is_active = payload.is_active
    await db.commit()
    await db.refresh(hook)
    return svc.webhook_read(hook)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: UUID,
    ctx: TenantContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> None:
    hook = await _load(db, ctx, webhook_id)
    await db.delete(hook)
    await db.commit()


@router.get("/{webhook_id}/deliveries", response_model=list[WebhookDeliveryRead])
async def list_deliveries(
    webhook_id: UUID,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = 50,
    ctx: TenantContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookDeliveryRead]:
    await _load(db, ctx, webhook_id)
    stmt = select(WebhookDelivery).where(WebhookDelivery.webhook_id == webhook_id)
    if status_filter:
        stmt = stmt.where(WebhookDelivery.status == status_filter)
    stmt = stmt.order_by(WebhookDelivery.created_at.desc()).limit(max(1, min(limit, 200)))
    rows = (await db.execute(stmt)).scalars().all()
    return [svc.delivery_read(delivery) for delivery in rows]


@router.post("/deliveries/{delivery_id}/replay", response_model=WebhookDeliveryRead)
async def replay_delivery(
    delivery_id: UUID,
    ctx: TenantContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> WebhookDeliveryRead:
    delivery = (
        await db.execute(
            select(WebhookDelivery).where(
                WebhookDelivery.id == delivery_id,
                WebhookDelivery.workspace_id == ctx.workspace.id,
            )
        )
    ).scalar_one_or_none()
    if delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")
    return svc.delivery_read(await svc.replay_delivery(db, delivery))
