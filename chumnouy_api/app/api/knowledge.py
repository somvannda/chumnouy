"""Knowledge base CRUD (v1).

Scopes: ``knowledge:read`` for reads, ``knowledge:write`` for writes. A console
user carries all scopes; an API key is limited to the scopes it was created with.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import TenantContext, require_tenant_scopes
from app.schemas import (
    KnowledgeArticleCreate,
    KnowledgeArticleRead,
    KnowledgeArticleUpdate,
)
from app.services import knowledge as svc

router = APIRouter(prefix="/knowledge/articles", tags=["knowledge"])

_read = require_tenant_scopes("knowledge:read")
_write = require_tenant_scopes("knowledge:write")


async def _get_article(db: AsyncSession, ctx: TenantContext, article_id: UUID):
    article = await svc.load_article(db, ctx.workspace.id, article_id)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return article


@router.get("", response_model=list[KnowledgeArticleRead])
async def list_articles(
    section: str | None = None,
    q: str | None = None,
    locale: str | None = None,
    active: bool | None = None,
    limit: int = 100,
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeArticleRead]:
    return await svc.list_articles(
        db, ctx.workspace.id, section=section, q=q, locale=locale, active=active, limit=limit
    )


@router.post("", response_model=KnowledgeArticleRead, status_code=status.HTTP_201_CREATED)
async def create_article(
    payload: KnowledgeArticleCreate,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeArticleRead:
    return await svc.create_article(db, ctx, payload)


@router.get("/{article_id}", response_model=KnowledgeArticleRead)
async def get_article(
    article_id: UUID,
    ctx: TenantContext = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeArticleRead:
    return svc.article_read(await _get_article(db, ctx, article_id))


@router.patch("/{article_id}", response_model=KnowledgeArticleRead)
async def update_article(
    article_id: UUID,
    payload: KnowledgeArticleUpdate,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeArticleRead:
    article = await _get_article(db, ctx, article_id)
    return await svc.update_article(db, article, payload)


@router.post("/{article_id}/restore", response_model=KnowledgeArticleRead)
async def restore_article(
    article_id: UUID,
    ctx: TenantContext = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeArticleRead:
    article = await _get_article(db, ctx, article_id)
    return await svc.restore_article(db, article)
