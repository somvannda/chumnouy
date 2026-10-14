"""Platform-operator router (``/api/admin``).

A separate credential from the tenant surfaces: only a console JWT whose user
has ``platform_role`` of ``admin``/``super_admin`` passes ``get_platform_admin``.
A tenant API key can never reach here (docs/architecture.md, Chmaba admin split).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_platform_admin
from app.models import User
from app.schemas import (
    AdminAccountRead,
    AdminUsageRead,
    AdminWorkspaceDetail,
    AdminWorkspaceSummary,
    AdminWorkspaceUpdate,
)
from app.services import admin as svc

router = APIRouter(tags=["admin"])

_admin = get_platform_admin


@router.get("/accounts", response_model=list[AdminAccountRead])
async def list_accounts(
    _admin_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminAccountRead]:
    return await svc.list_accounts(db)


@router.get("/workspaces", response_model=list[AdminWorkspaceSummary])
async def list_workspaces(
    q: str | None = None,
    active: bool | None = None,
    limit: int = 100,
    _admin_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminWorkspaceSummary]:
    return await svc.list_workspaces(db, q=q, active=active, limit=limit)


@router.get("/workspaces/{workspace_id}", response_model=AdminWorkspaceDetail)
async def workspace_detail(
    workspace_id: UUID,
    _admin_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminWorkspaceDetail:
    workspace = await svc.get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return await svc.workspace_detail(db, workspace)


@router.patch("/workspaces/{workspace_id}", response_model=AdminWorkspaceDetail)
async def update_workspace(
    workspace_id: UUID,
    payload: AdminWorkspaceUpdate,
    _admin_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminWorkspaceDetail:
    workspace = await svc.get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return await svc.update_workspace(db, workspace, payload)


@router.get("/usage", response_model=AdminUsageRead)
async def usage(
    _admin_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUsageRead:
    return await svc.usage_summary(db)
