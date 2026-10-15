"""Public help centre: read-only, unauthenticated access to a workspace's
active knowledge articles, addressed by workspace slug.

Publishing is per workspace and only exposes ``is_active`` articles, so the
public surface never leaks drafts or another workspace's content.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeArticle, Workspace
from app.schemas import HelpArticleRead, HelpArticleSummary, HelpIndex, HelpSection


def _summary(article: KnowledgeArticle) -> HelpArticleSummary:
    return HelpArticleSummary(
        slug=article.slug,
        title=article.title,
        summary=article.summary,
        section=article.section,
        locale=article.locale,
    )


async def workspace_by_slug(db: AsyncSession, slug: str) -> Workspace | None:
    return (
        await db.execute(
            select(Workspace).where(Workspace.slug == slug, Workspace.is_active.is_(True))
        )
    ).scalar_one_or_none()


async def index(
    db: AsyncSession,
    workspace: Workspace,
    *,
    section: str | None = None,
    q: str | None = None,
    locale: str | None = None,
) -> HelpIndex:
    base = select(KnowledgeArticle).where(
        KnowledgeArticle.workspace_id == workspace.id,
        KnowledgeArticle.is_active.is_(True),
    )
    if section:
        base = base.where(KnowledgeArticle.section == section)
    if locale:
        base = base.where(KnowledgeArticle.locale == locale)
    if q:
        like = f"%{q}%"
        base = base.where(
            or_(KnowledgeArticle.title.ilike(like), KnowledgeArticle.body.ilike(like))
        )

    counts = (
        await db.execute(
            select(KnowledgeArticle.section, func.count(KnowledgeArticle.id))
            .where(
                KnowledgeArticle.workspace_id == workspace.id,
                KnowledgeArticle.is_active.is_(True),
            )
            .group_by(KnowledgeArticle.section)
            .order_by(KnowledgeArticle.section)
        )
    ).all()
    rows = (
        await db.execute(
            base.order_by(KnowledgeArticle.position, KnowledgeArticle.title).limit(200)
        )
    ).scalars().all()
    return HelpIndex(
        workspace=workspace.slug,
        sections=[HelpSection(section=name, count=count) for name, count in counts],
        articles=[_summary(article) for article in rows],
    )


async def article(
    db: AsyncSession, workspace_id: UUID, slug: str, *, locale: str = "en"
) -> HelpArticleRead | None:
    row = (
        await db.execute(
            select(KnowledgeArticle).where(
                KnowledgeArticle.workspace_id == workspace_id,
                KnowledgeArticle.slug == slug,
                KnowledgeArticle.locale == locale,
                KnowledgeArticle.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return HelpArticleRead(
        slug=row.slug,
        title=row.title,
        summary=row.summary,
        section=row.section,
        locale=row.locale,
        body=row.body,
        updated_at=row.updated_at,
    )
