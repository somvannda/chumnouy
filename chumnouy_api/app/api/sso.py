"""Single sign-on (OIDC). Public: start + callback, addressed by workspace slug."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Workspace
from app.schemas import AuthRead, SsoStart
from app.services import sso as svc

router = APIRouter(prefix="/auth/sso", tags=["auth"])


@router.get("/callback", response_model=AuthRead)
async def callback(
    code: str = Query(min_length=1),
    state: str = Query(min_length=1),
    db: AsyncSession = Depends(get_db),
) -> AuthRead:
    """Handle the identity provider's redirect: exchange the code and sign in."""
    try:
        workspace_id = svc.parse_state(state)
    except svc.SsoError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    workspace = await db.get(Workspace, workspace_id)
    if workspace is None or not workspace.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    try:
        return await svc.complete_login(db, workspace, code)
    except svc.SsoError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{workspace_slug}", response_model=SsoStart)
async def start(workspace_slug: str, db: AsyncSession = Depends(get_db)) -> SsoStart:
    """Return the provider authorize URL + signed state for the app to redirect to."""
    workspace = (
        await db.execute(
            select(Workspace).where(
                Workspace.slug == workspace_slug, Workspace.is_active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if workspace is None or not svc.sso_enabled(workspace):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SSO is not enabled")
    state = svc.make_state(workspace)
    return SsoStart(authorize_url=svc.authorize_url(workspace, state=state), state=state)
