"""Teams: workspace-scoped groups of agents (routing / collaboration)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Team, TeamMember
from app.schemas import TeamCreate, TeamMemberAdd, TeamMemberRead, TeamRead, TeamUpdate
from app.security import slugify


async def _unique_slug(
    db: AsyncSession, workspace_id: UUID, base: str, *, exclude_id: UUID | None = None
) -> str:
    slug = slugify(base) or "team"
    candidate = slug
    suffix = 1
    while True:
        stmt = select(Team.id).where(Team.workspace_id == workspace_id, Team.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(Team.id != exclude_id)
        if (await db.execute(stmt)).scalar_one_or_none() is None:
            return candidate
        suffix += 1
        candidate = f"{slug}-{suffix}"


async def _members(db: AsyncSession, team_id: UUID) -> list[TeamMemberRead]:
    rows = (
        await db.execute(
            select(TeamMember).where(TeamMember.team_id == team_id).order_by(TeamMember.created_at)
        )
    ).scalars().all()
    return [TeamMemberRead(user_id=row.user_id, role=row.role) for row in rows]


async def team_read(db: AsyncSession, team: Team) -> TeamRead:
    return TeamRead(
        id=team.id,
        name=team.name,
        slug=team.slug,
        description=team.description,
        members=await _members(db, team.id),
        created_at=team.created_at,
    )


async def load_team(db: AsyncSession, workspace_id: UUID, team_id: UUID) -> Team | None:
    return (
        await db.execute(
            select(Team).where(Team.id == team_id, Team.workspace_id == workspace_id)
        )
    ).scalar_one_or_none()


async def list_teams(db: AsyncSession, workspace_id: UUID) -> list[TeamRead]:
    rows = (
        await db.execute(
            select(Team).where(Team.workspace_id == workspace_id).order_by(Team.created_at)
        )
    ).scalars().all()
    return [await team_read(db, team) for team in rows]


async def create_team(db: AsyncSession, workspace_id: UUID, payload: TeamCreate) -> TeamRead:
    team = Team(
        workspace_id=workspace_id,
        name=payload.name.strip(),
        slug=await _unique_slug(db, workspace_id, payload.name),
        description=payload.description,
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return await team_read(db, team)


async def update_team(db: AsyncSession, team: Team, payload: TeamUpdate) -> TeamRead:
    if payload.name is not None:
        team.name = payload.name.strip()
        team.slug = await _unique_slug(db, team.workspace_id, payload.name, exclude_id=team.id)
    if payload.description is not None:
        team.description = payload.description
    await db.commit()
    await db.refresh(team)
    return await team_read(db, team)


async def delete_team(db: AsyncSession, team: Team) -> None:
    await db.delete(team)
    await db.commit()


async def add_member(db: AsyncSession, team: Team, payload: TeamMemberAdd) -> TeamRead:
    existing = (
        await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team.id, TeamMember.user_id == payload.user_id
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(TeamMember(team_id=team.id, user_id=payload.user_id, role=payload.role))
    else:
        existing.role = payload.role
    await db.commit()
    return await team_read(db, team)


async def remove_member(db: AsyncSession, team: Team, user_id: UUID) -> TeamRead:
    existing = (
        await db.execute(
            select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.user_id == user_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        await db.delete(existing)
        await db.commit()
    return await team_read(db, team)
