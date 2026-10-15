"""Console-managed workspace settings, stored in ``workspace.settings``.

A workspace brings its own AI provider credentials and may override the Notifyr
hand-off; environment variables are the fallback. Secrets (AI key, Notifyr key)
are write-only — read models expose only a ``*_set`` flag.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.models import Workspace
from app.schemas import (
    AISettingsRead,
    AISettingsUpdate,
    LocaleUpdate,
    NotificationSettingsRead,
    NotificationSettingsUpdate,
    SlaSettingsUpdate,
    SsoSettingsRead,
    SsoSettingsUpdate,
    WorkspaceSettingsRead,
)
from app.services import ai as ai_service


def _stored(workspace: Workspace) -> dict:
    return dict(workspace.settings or {})


def _apply(workspace: Workspace, updates: dict) -> None:
    """Merge ``updates`` into ``workspace.settings``; ``None`` leaves, ``""`` clears."""
    stored = _stored(workspace)
    for key, value in updates.items():
        if value is None:
            continue
        cleaned = value.strip() if isinstance(value, str) else value
        if cleaned in ("", None):
            stored.pop(key, None)
        else:
            stored[key] = cleaned
    workspace.settings = stored


def ai_settings(workspace: Workspace) -> AISettingsRead:
    stored = _stored(workspace)
    effective_key = (stored.get("ai_api_key") or app_settings.ai_api_key or "").strip()
    return AISettingsRead(
        provider=stored.get("ai_provider"),
        model=stored.get("ai_model"),
        base_url=stored.get("ai_base_url"),
        api_key_set=bool(effective_key),
        providers=ai_service.provider_catalog(),
    )


def notification_settings(workspace: Workspace) -> NotificationSettingsRead:
    stored = _stored(workspace)
    url = (stored.get("notifyr_api_url") or app_settings.notifyr_api_url or "").strip() or None
    key = (stored.get("notifyr_api_key") or app_settings.notifyr_api_key or "").strip()
    return NotificationSettingsRead(notifyr_api_url=url, notifyr_api_key_set=bool(key))


def sso_settings(workspace: Workspace) -> SsoSettingsRead:
    sso = _stored(workspace).get("sso") or {}
    return SsoSettingsRead(
        enabled=bool(sso.get("enabled")),
        issuer=sso.get("issuer"),
        client_id=sso.get("client_id"),
        allowed_domains=list(sso.get("allowed_domains") or []),
        client_secret_set=bool(sso.get("client_secret")),
    )


def read(workspace: Workspace) -> WorkspaceSettingsRead:
    from app.services import sla as sla_svc

    return WorkspaceSettingsRead(
        locale=(workspace.settings or {}).get("locale") or "en",
        ai=ai_settings(workspace),
        notifications=notification_settings(workspace),
        sla=sla_svc.sla_settings(workspace),
        sso=sso_settings(workspace),
    )


async def update_sso(
    db: AsyncSession, workspace: Workspace, payload: SsoSettingsUpdate
) -> WorkspaceSettingsRead:
    stored = _stored(workspace)
    sso = dict(stored.get("sso") or {})
    if payload.enabled is not None:
        sso["enabled"] = payload.enabled
    if payload.issuer is not None:
        sso["issuer"] = payload.issuer.strip() or None
    if payload.client_id is not None:
        sso["client_id"] = payload.client_id.strip() or None
    if payload.client_secret is not None:
        if payload.client_secret.strip():
            sso["client_secret"] = payload.client_secret.strip()
        else:
            sso.pop("client_secret", None)
    if payload.allowed_domains is not None:
        sso["allowed_domains"] = [d.strip().lower() for d in payload.allowed_domains if d.strip()]
    stored["sso"] = {key: value for key, value in sso.items() if value is not None}
    workspace.settings = stored
    await db.commit()
    await db.refresh(workspace)
    return read(workspace)


async def update_sla(
    db: AsyncSession, workspace: Workspace, payload: "SlaSettingsUpdate"
) -> WorkspaceSettingsRead:
    from app.services import sla as sla_svc

    await sla_svc.update_settings(db, workspace, payload)
    return read(workspace)


async def update_locale(
    db: AsyncSession, workspace: Workspace, payload: "LocaleUpdate"
) -> WorkspaceSettingsRead:
    _apply(workspace, {"locale": payload.locale})
    await db.commit()
    await db.refresh(workspace)
    return read(workspace)


async def update_ai(
    db: AsyncSession, workspace: Workspace, payload: AISettingsUpdate
) -> AISettingsRead:
    _apply(
        workspace,
        {
            "ai_provider": payload.provider,
            "ai_model": payload.model,
            "ai_base_url": payload.base_url,
            "ai_api_key": payload.api_key,
        },
    )
    await db.commit()
    await db.refresh(workspace)
    return ai_settings(workspace)


async def update_notifications(
    db: AsyncSession, workspace: Workspace, payload: NotificationSettingsUpdate
) -> NotificationSettingsRead:
    _apply(
        workspace,
        {
            "notifyr_api_url": payload.notifyr_api_url,
            "notifyr_api_key": payload.notifyr_api_key,
        },
    )
    await db.commit()
    await db.refresh(workspace)
    return notification_settings(workspace)
