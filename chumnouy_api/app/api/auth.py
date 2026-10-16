"""Console authentication: signup, login and the current user.

Signup creates the whole tenant spine in one transaction — Account → Workspace →
owner Membership — so an integrator can take an API key immediately after.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import Account, Membership, User, Workspace
from app.schemas import (
    AuthRead,
    InviteAccept,
    LoginRequest,
    MeRead,
    SignupRequest,
    UserRead,
    WorkspaceRead,
)
from app.security import create_access_token, hash_password, slugify, verify_password
from app.services import knowledge as knowledge_svc
from app.services import members as members_svc

router = APIRouter(prefix="/auth", tags=["auth"])


async def _unique_slug(db: AsyncSession, model, base: str) -> str:
    slug = slugify(base)
    candidate = slug
    suffix = 1
    while (await db.execute(select(model.id).where(model.slug == candidate))).scalar_one_or_none() is not None:
        suffix += 1
        candidate = f"{slug}-{suffix}"
    return candidate


async def _primary_workspace(db: AsyncSession, user_id) -> tuple[Membership, Workspace] | None:
    rows = (
        await db.execute(
            select(Membership, Workspace)
            .join(Workspace, Workspace.id == Membership.workspace_id)
            .where(
                Membership.user_id == user_id,
                Membership.status == "active",
                Workspace.is_active.is_(True),
            )
            .order_by(Membership.created_at)
        )
    ).all()
    if not rows:
        return None
    owners = [(m, w) for m, w in rows if m.role == "owner"]
    return owners[0] if owners else rows[0]


@router.post("/signup", response_model=AuthRead, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, db: AsyncSession = Depends(get_db)) -> AuthRead:
    email = payload.email.lower()
    existing = (await db.execute(select(User.id).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    workspace_name = (payload.workspace_name or f"{payload.name}'s workspace").strip()

    account = Account(name=workspace_name, slug=await _unique_slug(db, Account, workspace_name))
    db.add(account)
    await db.flush()

    workspace = Workspace(
        account_id=account.id,
        name=workspace_name,
        slug=await _unique_slug(db, Workspace, workspace_name),
    )
    db.add(workspace)
    await db.flush()

    user = User(
        email=email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()

    db.add(Membership(workspace_id=workspace.id, user_id=user.id, role="owner"))
    # Every workspace starts with a seeded help corpus (docs/handoff.md C3).
    await knowledge_svc.seed_defaults(db, workspace.id)
    await db.commit()
    await db.refresh(user)
    await db.refresh(workspace)

    return AuthRead(
        token=create_access_token(user.id),
        user=UserRead.model_validate(user),
        workspace=WorkspaceRead(id=workspace.id, name=workspace.name, slug=workspace.slug, role="owner"),
    )


@router.post("/login", response_model=AuthRead)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthRead:
    email = payload.email.lower()
    user = (
        await db.execute(select(User).where(User.email == email, User.is_active.is_(True)))
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    primary = await _primary_workspace(db, user.id)
    if primary is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has no active workspace",
        )
    membership, workspace = primary
    return AuthRead(
        token=create_access_token(user.id),
        user=UserRead.model_validate(user),
        workspace=WorkspaceRead(id=workspace.id, name=workspace.name, slug=workspace.slug, role=membership.role),
    )


@router.post("/invite/accept", response_model=AuthRead)
async def accept_invite(payload: InviteAccept, db: AsyncSession = Depends(get_db)) -> AuthRead:
    """Consume a workspace invitation and sign the new member in."""
    try:
        return await members_svc.accept(
            db, token=payload.token, password=payload.password, name=payload.name
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except members_svc.MemberError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/me", response_model=MeRead)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeRead:
    rows = (
        await db.execute(
            select(Membership, Workspace)
            .join(Workspace, Workspace.id == Membership.workspace_id)
            .where(Membership.user_id == user.id, Membership.status == "active")
            .order_by(Membership.created_at)
        )
    ).all()
    return MeRead(
        user=UserRead.model_validate(user),
        workspaces=[
            WorkspaceRead(id=w.id, name=w.name, slug=w.slug, role=m.role) for m, w in rows
        ],
    )
