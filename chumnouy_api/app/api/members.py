"""Workspace members and invitations (console).

Reading the roster needs any console session (assignment pickers use it); every
write requires the ``members:manage`` permission (owner/admin). Writes are also
recorded in the workspace audit trail (``member.*`` / ``invite.*``).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import WorkspaceContext, get_workspace_context, require_permission
from app.schemas import MemberInvite, MemberInviteRead, MemberRead, MemberUpdate
from app.services import audit as audit_svc
from app.services import members as svc

router = APIRouter(prefix="/members", tags=["members"])

_manage = require_permission("members:manage")


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


async def _audit(db: AsyncSession, ctx: WorkspaceContext, type: str, **data) -> None:
    audit_svc.record_workspace_event(
        db,
        ctx.workspace.id,
        type=type,
        actor_type="user",
        actor_id=ctx.user.id,
        data=data,
    )
    await db.commit()


@router.get("", response_model=list[MemberRead])
async def list_members(
    ctx: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[MemberRead]:
    return await svc.list_members(db, ctx.workspace.id)


# Declared before ``/{user_id}`` so the literal path wins.
@router.get("/invites", response_model=list[MemberInviteRead])
async def list_invites(
    ctx: WorkspaceContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> list[MemberInviteRead]:
    return await svc.list_invites(db, ctx.workspace.id)


@router.post("/invites", response_model=MemberInviteRead, status_code=status.HTTP_201_CREATED)
async def invite_member(
    payload: MemberInvite,
    ctx: WorkspaceContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> MemberInviteRead:
    try:
        result = await svc.invite(db, ctx.workspace, payload, invited_by_user_id=ctx.user.id)
    except svc.MemberError as exc:
        raise _translate(exc) from exc
    await _audit(db, ctx, "member.invited", email=result.email, role=result.role, status=result.status)
    return result


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    invite_id: UUID,
    ctx: WorkspaceContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await svc.revoke_invite(db, ctx.workspace.id, invite_id)
    except LookupError as exc:
        raise _translate(exc) from exc
    await _audit(db, ctx, "invite.revoked", invite_id=str(invite_id))


@router.patch("/{user_id}", response_model=MemberRead)
async def update_member(
    user_id: UUID,
    payload: MemberUpdate,
    ctx: WorkspaceContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> MemberRead:
    if payload.role is None and payload.skills is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update"
        )
    try:
        result = await svc.update_member(
            db, ctx.workspace.id, user_id, role=payload.role, skills=payload.skills
        )
    except (svc.MemberError, LookupError) as exc:
        raise _translate(exc) from exc
    await _audit(
        db,
        ctx,
        "member.updated",
        user_id=str(user_id),
        role=result.role,
        skills=list(result.skills or []),
    )
    return result


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: UUID,
    ctx: WorkspaceContext = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await svc.remove(db, ctx.workspace.id, user_id, actor_user_id=ctx.user.id)
    except (svc.MemberError, LookupError) as exc:
        raise _translate(exc) from exc
    await _audit(db, ctx, "member.removed", user_id=str(user_id))
