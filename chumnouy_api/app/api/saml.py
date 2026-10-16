"""SAML 2.0 SP endpoints: metadata, the IdP hand-off and the ACS callback.

``GET  /v1/auth/saml/{workspace_slug}/metadata``  — SP metadata for the IdP admin
``GET  /v1/auth/saml/{workspace_slug}/start``     — where to send the browser
``POST /v1/auth/saml/{workspace_slug}/acs``       — consume the IdP response
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import AuthRead, SamlStart
from app.services import saml as svc

router = APIRouter(prefix="/auth/saml", tags=["auth"])


async def _workspace(db: AsyncSession, workspace_slug: str):
    from app.services import help_centre as help_svc

    workspace = await help_svc.workspace_by_slug(db, workspace_slug)
    if workspace is None or not svc.saml_enabled(workspace):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SAML is not enabled")
    return workspace


@router.get("/{workspace_slug}/metadata")
async def saml_metadata(
    workspace_slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    workspace = await _workspace(db, workspace_slug)
    xml = svc.metadata(workspace, str(request.base_url))
    return Response(content=xml, media_type="application/samlmetadata+xml")


@router.get("/{workspace_slug}/start", response_model=SamlStart)
async def saml_start(
    workspace_slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SamlStart:
    workspace = await _workspace(db, workspace_slug)
    return svc.start(workspace, str(request.base_url))


@router.post("/{workspace_slug}/acs", response_model=AuthRead)
async def saml_acs(
    workspace_slug: str,
    SAMLResponse: str = Form(...),
    RelayState: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> AuthRead:
    """Consume the IdP's signed assertion and sign the user in."""
    workspace = await _workspace(db, workspace_slug)
    try:
        return await svc.login(db, workspace, SAMLResponse)
    except svc.SamlNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except svc.SamlInvalid as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
