"""Workspace members and invitations.

Owners/admins invite by email. An existing user is added straight away; anyone
else gets a one-time invitation token — delivery of the link is Notifyr's job, so
the console simply shows it. Accepting creates the ``User`` and the ``Membership``
(``Membership.user_id`` is not nullable, which is why the invite stands alone
until then). The workspace owner can never be demoted or removed.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Membership, User, Workspace, WorkspaceInvite, utcnow
from app.schemas import (
    AuthRead,
    MemberInvite,
    MemberInviteRead,
    MemberRead,
    UserRead,
    WorkspaceRead,
)
from app.security import create_access_token, hash_password, hash_token
from app.services import quota as quota_svc

INVITE_TTL_DAYS = 7
INVITE_PREFIX = "inv"
MAX_SKILLS = 20
MAX_SKILL_LENGTH = 40


def normalize_skills(values: list[str] | None) -> list[str]:
    """Lower-case, trim, drop blanks/duplicates and cap the list (routing tokens)."""
    result: list[str] = []
    for value in values or []:
        skill = str(value).strip().lower()[:MAX_SKILL_LENGTH]
        if skill and skill not in result:
            result.append(skill)
        if len(result) >= MAX_SKILLS:
            break
    return result


class MemberError(Exception):
    """A membership rule was violated (the router maps this to a 4xx)."""


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _member_read(membership: Membership, user: User) -> MemberRead:
    return MemberRead(
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=membership.role,
        status=membership.status,
        created_at=membership.created_at,
        skills=list(membership.skills or []),
    )


def _invite_read(invite: WorkspaceInvite, *, token: str | None = None) -> MemberInviteRead:
    return MemberInviteRead(
        id=invite.id,
        email=invite.email,
        role=invite.role,
        status=invite.status,
        expires_at=invite.expires_at,
        accepted_at=invite.accepted_at,
        token=token,
    )


async def list_members(db: AsyncSession, workspace_id: UUID) -> list[MemberRead]:
    rows = (
        await db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.workspace_id == workspace_id)
            .order_by(Membership.created_at)
        )
    ).all()
    return [_member_read(membership, user) for membership, user in rows]


async def list_invites(db: AsyncSession, workspace_id: UUID) -> list[MemberInviteRead]:
    rows = (
        await db.execute(
            select(WorkspaceInvite)
            .where(WorkspaceInvite.workspace_id == workspace_id)
            .order_by(WorkspaceInvite.created_at.desc())
        )
    ).scalars().all()
    return [_invite_read(row) for row in rows]


async def _user_by_email(db: AsyncSession, email: str) -> User | None:
    return (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()


async def _membership(db: AsyncSession, workspace_id: UUID, user_id: UUID) -> Membership | None:
    return (
        await db.execute(
            select(Membership).where(
                Membership.workspace_id == workspace_id, Membership.user_id == user_id
            )
        )
    ).scalar_one_or_none()


async def invite(
    db: AsyncSession,
    workspace: Workspace,
    payload: MemberInvite,
    *,
    invited_by_user_id: UUID | None = None,
) -> MemberInviteRead:
    """Add an existing user, or queue a one-time invitation for a new one."""
    await quota_svc.enforce_seat_quota(db, workspace)
    email = payload.email.lower()
    user = await _user_by_email(db, email)
    if user is not None:
        existing = await _membership(db, workspace.id, user.id)
        if existing is not None and existing.status == "active":
            raise MemberError(f"{email} is already a member of this workspace")
        if existing is not None:
            existing.role = payload.role
            existing.status = "active"
        else:
            db.add(
                Membership(
                    workspace_id=workspace.id, user_id=user.id, role=payload.role, status="active"
                )
            )
        await db.commit()
        now = utcnow()
        return MemberInviteRead(
            id=user.id, email=email, role=payload.role, status="accepted", expires_at=now, accepted_at=now
        )

    token = f"{INVITE_PREFIX}_{secrets.token_urlsafe(32)}"
    expires_at = utcnow() + timedelta(days=INVITE_TTL_DAYS)
    pending = (
        await db.execute(
            select(WorkspaceInvite).where(
                WorkspaceInvite.workspace_id == workspace.id, WorkspaceInvite.email == email
            )
        )
    ).scalar_one_or_none()
    if pending is None:
        pending = WorkspaceInvite(
            workspace_id=workspace.id,
            email=email,
            name=payload.name,
            role=payload.role,
            token_hash=hash_token(token),
            invited_by_user_id=invited_by_user_id,
            status="pending",
            expires_at=expires_at,
        )
        db.add(pending)
    else:
        if pending.status == "pending":
            raise MemberError(f"{email} already has a pending invitation")
        # Re-inviting a revoked or accepted address issues a fresh token.
        pending.role = payload.role
        pending.name = payload.name
        pending.token_hash = hash_token(token)
        pending.status = "pending"
        pending.expires_at = expires_at
        pending.accepted_at = None
    await db.commit()
    await db.refresh(pending)
    return _invite_read(pending, token=token)


async def revoke_invite(db: AsyncSession, workspace_id: UUID, invite_id: UUID) -> None:
    invite_row = (
        await db.execute(
            select(WorkspaceInvite).where(
                WorkspaceInvite.id == invite_id, WorkspaceInvite.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()
    if invite_row is None:
        raise LookupError("Invitation not found")
    await db.delete(invite_row)
    await db.commit()


async def update_member(
    db: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    *,
    role: str | None = None,
    skills: list[str] | None = None,
) -> MemberRead:
    membership = await _membership(db, workspace_id, user_id)
    if membership is None:
        raise LookupError("Member not found")
    if role is not None:
        if membership.role == "owner":
            raise MemberError("The workspace owner's role cannot be changed")
        membership.role = role
    if skills is not None:
        membership.skills = normalize_skills(skills)
    await db.commit()
    await db.refresh(membership)
    user = await db.get(User, user_id)
    return _member_read(membership, user)


async def remove(db: AsyncSession, workspace_id: UUID, user_id: UUID, *, actor_user_id: UUID) -> None:
    membership = await _membership(db, workspace_id, user_id)
    if membership is None:
        raise LookupError("Member not found")
    if membership.role == "owner":
        raise MemberError("The workspace owner cannot be removed")
    if user_id == actor_user_id:
        raise MemberError("You cannot remove yourself")
    await db.delete(membership)
    await db.commit()


async def accept(db: AsyncSession, *, token: str, password: str, name: str | None = None) -> AuthRead:
    """Consume an invitation: create the user if needed and sign them in."""
    invite_row = (
        await db.execute(
            select(WorkspaceInvite).where(WorkspaceInvite.token_hash == hash_token(token))
        )
    ).scalar_one_or_none()
    if invite_row is None:
        raise LookupError("This invitation link is not valid")
    if invite_row.status != "pending":
        raise MemberError("This invitation has already been used")
    if _aware(invite_row.expires_at) < utcnow():
        raise MemberError("This invitation has expired")
    workspace = await db.get(Workspace, invite_row.workspace_id)
    if workspace is None:
        raise LookupError("This invitation is no longer valid")
    await quota_svc.enforce_seat_quota(db, workspace)

    user = await _user_by_email(db, invite_row.email)
    if user is None:
        display = (name or invite_row.name or invite_row.email.split("@")[0]).strip()
        user = User(email=invite_row.email, name=display, password_hash=hash_password(password))
        db.add(user)
        await db.flush()
    elif name:
        # An existing account keeps its own password and joins with the new name.
        user.name = name.strip()

    membership = await _membership(db, workspace.id, user.id)
    if membership is None:
        membership = Membership(
            workspace_id=workspace.id, user_id=user.id, role=invite_row.role, status="active"
        )
        db.add(membership)
    else:
        membership.role = invite_row.role
        membership.status = "active"

    invite_row.status = "accepted"
    invite_row.accepted_at = utcnow()
    await db.commit()
    await db.refresh(user)
    return AuthRead(
        token=create_access_token(user.id),
        user=UserRead.model_validate(user),
        workspace=WorkspaceRead(
            id=workspace.id, name=workspace.name, slug=workspace.slug, role=membership.role
        ),
    )
