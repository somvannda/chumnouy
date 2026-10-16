"""Public help centre (unauthenticated). Addressed by workspace slug; only
active knowledge articles are exposed. Rate-limited by the public middleware."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import HelpArticleFeedbackCreate, HelpArticleFeedbackRead, HelpArticleRead, HelpIndex
from app.services import help_centre as svc

router = APIRouter(prefix="/public/help", tags=["help-centre"])


async def _workspace(db: AsyncSession, workspace_slug: str):
    workspace = await svc.workspace_by_slug(db, workspace_slug)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Help centre not found")
    return workspace


@router.get("/{workspace_slug}", response_model=HelpIndex)
async def help_index(
    workspace_slug: str,
    section: str | None = None,
    q: str | None = None,
    locale: str | None = Query(default=None, max_length=5),
    db: AsyncSession = Depends(get_db),
) -> HelpIndex:
    workspace = await _workspace(db, workspace_slug)
    return await svc.index(db, workspace, section=section, q=q, locale=locale)


@router.get("/{workspace_slug}/articles/{article_slug}", response_model=HelpArticleRead)
async def help_article(
    workspace_slug: str,
    article_slug: str,
    locale: str = Query(default="en", max_length=5),
    db: AsyncSession = Depends(get_db),
) -> HelpArticleRead:
    workspace = await _workspace(db, workspace_slug)
    article = await svc.article(db, workspace.id, article_slug, locale=locale)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return article


@router.post(
    "/{workspace_slug}/articles/{article_slug}/feedback",
    response_model=HelpArticleFeedbackRead,
    status_code=status.HTTP_201_CREATED,
)
async def help_article_feedback(
    workspace_slug: str,
    article_slug: str,
    payload: HelpArticleFeedbackCreate,
    locale: str = Query(default="en", max_length=5),
    db: AsyncSession = Depends(get_db),
) -> HelpArticleFeedbackRead:
    """Record whether a help article was helpful (public, rate-limited)."""
    workspace = await _workspace(db, workspace_slug)
    feedback = await svc.submit_feedback(
        db,
        workspace.id,
        article_slug,
        helpful=payload.helpful,
        comment=payload.comment,
        locale=locale,
    )
    if feedback is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return feedback
