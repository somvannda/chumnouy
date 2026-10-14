"""Console settings for the current workspace (owner/admin only).

AI provider credentials and the Notifyr override live in ``workspace.settings``;
secrets (``api_key``, ``notifyr_api_key``) are write-only — set them here, read
only a ``*_set`` flag back.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import WorkspaceContext, require_workspace_roles
from app.schemas import (
    AISettingsRead,
    AISettingsUpdate,
    NotificationSettingsRead,
    NotificationSettingsUpdate,
    WorkspaceSettingsRead,
)
from app.services import workspace_settings as svc

router = APIRouter(prefix="/console", tags=["console"])

_owner = require_workspace_roles("owner", "admin")


@router.get("/settings", response_model=WorkspaceSettingsRead)
async def get_settings(ctx: WorkspaceContext = Depends(_owner)) -> WorkspaceSettingsRead:
    return svc.read(ctx.workspace)


@router.patch("/settings/ai", response_model=AISettingsRead)
async def update_ai(
    payload: AISettingsUpdate,
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> AISettingsRead:
    return await svc.update_ai(db, ctx.workspace, payload)


@router.patch("/settings/notifications", response_model=NotificationSettingsRead)
async def update_notifications(
    payload: NotificationSettingsUpdate,
    ctx: WorkspaceContext = Depends(_owner),
    db: AsyncSession = Depends(get_db),
) -> NotificationSettingsRead:
    return await svc.update_notifications(db, ctx.workspace, payload)
