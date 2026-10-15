"""Teams CRUD (console). Requires the ``teams:manage`` permission."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import WorkspaceContext, require_permission
from app.schemas import TeamCreate, TeamMemberAdd, TeamRead, TeamUpdate
from app.services import teams as svc

router = APIRouter(prefix="/teams", tags=["teams"])

_manage = require_permission("teams:manage")


async def _load(db: AsyncSession, ctx: WorkspaceContext, team_id: UUID):
    team = await svc.load_team(db, ctx.workspace.id, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


@router.get("", response_model=list[TeamRead])
async def list_teams(
    ctx: WorkspaceContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> list[TeamRead]:
    return await svc.list_teams(db, ctx.workspace.id)


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreate,
    ctx: WorkspaceContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> TeamRead:
    return await svc.create_team(db, ctx.workspace.id, payload)


@router.get("/{team_id}", response_model=TeamRead)
async def get_team(
    team_id: UUID,
    ctx: WorkspaceContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> TeamRead:
    return await svc.team_read(db, await _load(db, ctx, team_id))


@router.patch("/{team_id}", response_model=TeamRead)
async def update_team(
    team_id: UUID,
    payload: TeamUpdate,
    ctx: WorkspaceContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> TeamRead:
    return await svc.update_team(db, await _load(db, ctx, team_id), payload)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: UUID,
    ctx: WorkspaceContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> None:
    await svc.delete_team(db, await _load(db, ctx, team_id))


@router.post("/{team_id}/members", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
async def add_member(
    team_id: UUID,
    payload: TeamMemberAdd,
    ctx: WorkspaceContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> TeamRead:
    return await svc.add_member(db, await _load(db, ctx, team_id), payload)


@router.delete("/{team_id}/members/{user_id}", response_model=TeamRead)
async def remove_member(
    team_id: UUID,
    user_id: UUID,
    ctx: WorkspaceContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> TeamRead:
    return await svc.remove_member(db, await _load(db, ctx, team_id), user_id)
