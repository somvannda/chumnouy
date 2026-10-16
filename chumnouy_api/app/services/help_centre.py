"""Public help centre: read-only, unauthenticated access to a workspace's
active knowledge articles, addressed by workspace slug.

Publishing is per workspace and only exposes ``is_active`` articles, so the
public surface never leaks drafts or another workspace's content.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HelpArticleFeedback, KnowledgeArticle, Workspace
from app.schemas import (
    HelpArticleFeedbackRead,
    HelpArticleRead,
    HelpArticleSummary,
    HelpIndex,
    HelpSection,
)


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
    yes, no = await feedback_counts(db, row.id)
    return HelpArticleRead(
        slug=row.slug,
        title=row.title,
        summary=row.summary,
        section=row.section,
        locale=row.locale,
        body=row.body,
        updated_at=row.updated_at,
        helpful_yes=yes,
        helpful_no=no,
    )


async def feedback_counts(db: AsyncSession, article_id: UUID) -> tuple[int, int]:
    """``(helpful, not helpful)`` for one article."""
    rows = (
        await db.execute(
            select(HelpArticleFeedback.helpful, func.count(HelpArticleFeedback.id))
            .where(HelpArticleFeedback.article_id == article_id)
            .group_by(HelpArticleFeedback.helpful)
        )
    ).all()
    counts = {bool(helpful): int(count) for helpful, count in rows}
    return counts.get(True, 0), counts.get(False, 0)


async def submit_feedback(
    db: AsyncSession,
    workspace_id: UUID,
    slug: str,
    *,
    helpful: bool,
    comment: str | None = None,
    locale: str = "en",
) -> HelpArticleFeedbackRead | None:
    """Record a reader's verdict. Returns ``None`` when the article is unknown."""
    article_row = (
        await db.execute(
            select(KnowledgeArticle).where(
                KnowledgeArticle.workspace_id == workspace_id,
                KnowledgeArticle.slug == slug,
                KnowledgeArticle.locale == locale,
                KnowledgeArticle.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if article_row is None:
        return None
    feedback = HelpArticleFeedback(
        workspace_id=workspace_id,
        article_id=article_row.id,
        helpful=helpful,
        comment=(comment or "").strip() or None,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return HelpArticleFeedbackRead(
        helpful=feedback.helpful,
        comment=feedback.comment,
        created_at=feedback.created_at,
    )
