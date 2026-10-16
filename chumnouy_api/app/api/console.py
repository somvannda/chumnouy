"""Console settings for the current workspace (owner/admin only).

AI provider credentials and the Notifyr override live in ``workspace.settings``;
secrets (``api_key``, ``notifyr_api_key``) are write-only — set them here, read
only a ``*_set`` flag back.

Every change is recorded in the workspace audit trail (``settings.*``), with
secret fields stripped from the recorded payload.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import WorkspaceContext, require_permission
from app.schemas import (
    AISettingsRead,
    AISettingsUpdate,
    BrandingUpdate,
    BusinessHoursUpdate,
    LocaleUpdate,
    NotificationSettingsRead,
    NotificationSettingsUpdate,
    RetentionSettingsUpdate,
    SecuritySettingsUpdate,
    SlaSettingsUpdate,
    SsoSettingsUpdate,
    WorkspaceSettingsRead,
)
from app.services import audit as audit_svc
from app.services import workspace_settings as svc

router = APIRouter(prefix="/console", tags=["console"])

_owner = require_permission("settings:manage")

# Never copy these into the audit trail.
_SECRET_FIELDS = {"api_key", "notifyr_api_key", "client_secret"}


async def _audit(
    db: AsyncSession, ctx: WorkspaceContext, section: str, payload=None
) -> None:
    data = (
        payload.model_dump(exclude_none=True, exclude=_SECRET_FIELDS) if payload is not None else {}
    )
    audit_svc.record_workspace_event(
        db,
        ctx.workspace.id,
        type=f"settings.{section}",
        actor_type="user",
        actor_id=ctx.user.id,
        data=data,
    )
    await db.commit()


@router.get("/settings", response_model=WorkspaceSettingsRead)
async def get_settings(ctx: WorkspaceContext = Depends(_owner)) -> WorkspaceSettingsRead:
    return svc.read(ctx.workspace)


@router.patch("/settings/ai", response_model=AISettingsRead)
async def update_ai(
    payload: AISettingsUpdate,
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> AISettingsRead:
    result = await svc.update_ai(db, ctx.workspace, payload)
    await _audit(db, ctx, "ai", payload)
    return result


@router.patch("/settings/notifications", response_model=NotificationSettingsRead)
async def update_notifications(
    payload: NotificationSettingsUpdate,
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> NotificationSettingsRead:
    result = await svc.update_notifications(db, ctx.workspace, payload)
    await _audit(db, ctx, "notifications", payload)
    return result


@router.patch("/settings/locale", response_model=WorkspaceSettingsRead)
async def update_locale(
    payload: LocaleUpdate,
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceSettingsRead:
    result = await svc.update_locale(db, ctx.workspace, payload)
    await _audit(db, ctx, "locale", payload)
    return result


@router.patch("/settings/sla", response_model=WorkspaceSettingsRead)
async def update_sla(
    payload: SlaSettingsUpdate,
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceSettingsRead:
    result = await svc.update_sla(db, ctx.workspace, payload)
    await _audit(db, ctx, "sla", payload)
    return result


@router.patch("/settings/sso", response_model=WorkspaceSettingsRead)
async def update_sso(
    payload: SsoSettingsUpdate,
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceSettingsRead:
    result = await svc.update_sso(db, ctx.workspace, payload)
    await _audit(db, ctx, "sso", payload)
    return result


@router.patch("/settings/business-hours", response_model=WorkspaceSettingsRead)
async def update_business_hours(
    payload: BusinessHoursUpdate,
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceSettingsRead:
    result = await svc.update_business_hours(db, ctx.workspace, payload)
    await _audit(db, ctx, "business-hours", payload)
    return result


@router.patch("/settings/branding", response_model=WorkspaceSettingsRead)
async def update_branding(
    payload: BrandingUpdate,
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceSettingsRead:
    result = await svc.update_branding(db, ctx.workspace, payload)
    await _audit(db, ctx, "branding", payload)
    return result


@router.patch("/settings/security", response_model=WorkspaceSettingsRead)
async def update_security(
    payload: SecuritySettingsUpdate,
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceSettingsRead:
    result = await svc.update_security(db, ctx.workspace, payload)
    await _audit(db, ctx, "security", payload)
    return result


@router.patch("/settings/retention", response_model=WorkspaceSettingsRead)
async def update_retention(
    payload: RetentionSettingsUpdate,
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceSettingsRead:
    result = await svc.update_retention(db, ctx.workspace, payload)
    await _audit(db, ctx, "retention", payload)
    return result
