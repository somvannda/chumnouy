"""Workspace-scoped help corpus.

Articles are the grounding material for the AI assistant (C4) and the help
centre. Ported concept from Chmaba POS ``help_repo`` / ``support_content``: the
seeded default articles become a per-workspace starting corpus rather than a
single global one. Articles are soft-deleted via ``is_active`` and restorable.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import TenantContext
from app.models import KnowledgeArticle
from app.schemas import (
    KnowledgeArticleCreate,
    KnowledgeArticleRead,
    KnowledgeArticleUpdate,
)
from app.security import slugify

# The default corpus every new workspace starts from — generic support content,
# not product-specific, so it reads as a template to edit or delete.
DEFAULT_ARTICLES: tuple[dict[str, str], ...] = (
    {
        "section": "getting-started",
        "title": "How support works",
        "summary": "What a ticket is and how it moves to resolved.",
        "body": (
            "Every request becomes a ticket with a short reference (for example "
            "CMY-1042). A ticket starts open, may move to pending while we wait on "
            "you, and is resolved once answered. Reopen a resolved ticket any time "
            "by replying to it."
        ),
    },
    {
        "section": "getting-started",
        "title": "Contacting support",
        "summary": "How to reach the team and what to include.",
        "body": (
            "Open a ticket from this product or reply to an existing one. Include "
            "what you expected, what happened, and any order or store reference. "
            "Attach a screenshot if it helps."
        ),
    },
    {
        "section": "account",
        "title": "Adding teammates",
        "summary": "Invite people to your workspace.",
        "body": (
            "Workspace owners and admins can invite teammates. Each person signs in "
            "with their own email and sees only the workspaces they belong to."
        ),
    },
    {
        "section": "billing",
        "title": "Invoices and receipts",
        "summary": "Where to find billing documents.",
        "body": (
            "Billing documents are issued per account. Ask support if a receipt is "
            "missing and include the invoice number."
        ),
    },
)


def article_read(article: KnowledgeArticle) -> KnowledgeArticleRead:
    return KnowledgeArticleRead(
        id=article.id,
        slug=article.slug,
        title=article.title,
        summary=article.summary,
        body=article.body,
        section=article.section,
        locale=article.locale,
        verticals=list(article.verticals or []),
        roles=list(article.roles or []),
        position=article.position,
        is_active=article.is_active,
        created_at=article.created_at,
        updated_at=article.updated_at,
    )


async def _unique_slug(
    db: AsyncSession,
    workspace_id: UUID,
    base: str,
    locale: str,
    *,
    exclude_id: UUID | None = None,
) -> str:
    slug = slugify(base) or "article"
    candidate = slug
    suffix = 1
    while True:
        stmt = select(KnowledgeArticle.id).where(
            KnowledgeArticle.workspace_id == workspace_id,
            KnowledgeArticle.locale == locale,
            KnowledgeArticle.slug == candidate,
        )
        if exclude_id is not None:
            stmt = stmt.where(KnowledgeArticle.id != exclude_id)
        if (await db.execute(stmt)).scalar_one_or_none() is None:
            return candidate
        suffix += 1
        candidate = f"{slug}-{suffix}"


async def load_article(
    db: AsyncSession, workspace_id: UUID, article_id: UUID
) -> KnowledgeArticle | None:
    return (
        await db.execute(
            select(KnowledgeArticle).where(
                KnowledgeArticle.id == article_id,
                KnowledgeArticle.workspace_id == workspace_id,
            )
        )
    ).scalar_one_or_none()


async def list_articles(
    db: AsyncSession,
    workspace_id: UUID,
    *,
    section: str | None = None,
    q: str | None = None,
    locale: str | None = None,
    active: bool | None = None,
    limit: int = 100,
) -> list[KnowledgeArticleRead]:
    stmt = select(KnowledgeArticle).where(KnowledgeArticle.workspace_id == workspace_id)
    if section:
        stmt = stmt.where(KnowledgeArticle.section == section)
    if locale:
        stmt = stmt.where(KnowledgeArticle.locale == locale)
    if active is not None:
        stmt = stmt.where(KnowledgeArticle.is_active.is_(active))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(KnowledgeArticle.title.ilike(like), KnowledgeArticle.body.ilike(like))
        )
    stmt = (
        stmt.order_by(KnowledgeArticle.position, KnowledgeArticle.created_at)
        .limit(max(1, min(limit, 200)))
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [article_read(article) for article in rows]


async def create_article(
    db: AsyncSession, ctx: TenantContext, payload: KnowledgeArticleCreate
) -> KnowledgeArticleRead:
    slug = await _unique_slug(db, ctx.workspace.id, payload.slug or payload.title, payload.locale)
    article = KnowledgeArticle(
        workspace_id=ctx.workspace.id,
        slug=slug,
        title=payload.title.strip(),
        summary=payload.summary,
        body=payload.body,
        section=payload.section.strip() or "general",
        locale=payload.locale,
        verticals=payload.verticals,
        roles=payload.roles,
        position=payload.position,
        is_active=payload.is_active,
        created_by=ctx.user.id if ctx.user else None,
    )
    db.add(article)
    await db.commit()
    await db.refresh(article)
    return article_read(article)


async def update_article(
    db: AsyncSession, article: KnowledgeArticle, payload: KnowledgeArticleUpdate
) -> KnowledgeArticleRead:
    if payload.title is not None:
        article.title = payload.title.strip()
    if payload.summary is not None:
        article.summary = payload.summary
    if payload.body is not None:
        article.body = payload.body
    if payload.section is not None:
        article.section = payload.section.strip() or "general"
    if payload.locale is not None and payload.locale != article.locale:
        article.locale = payload.locale
        article.slug = await _unique_slug(
            db, article.workspace_id, article.slug, payload.locale, exclude_id=article.id
        )
    if payload.verticals is not None:
        article.verticals = payload.verticals
    if payload.roles is not None:
        article.roles = payload.roles
    if payload.position is not None:
        article.position = payload.position
    if payload.is_active is not None:
        article.is_active = payload.is_active
    await db.commit()
    await db.refresh(article)
    return article_read(article)


async def restore_article(
    db: AsyncSession, article: KnowledgeArticle
) -> KnowledgeArticleRead:
    article.is_active = True
    await db.commit()
    await db.refresh(article)
    return article_read(article)


async def seed_defaults(db: AsyncSession, workspace_id: UUID) -> int:
    """Seed the default corpus once for a new workspace (idempotent, no commit)."""
    existing = (
        await db.execute(
            select(KnowledgeArticle.id)
            .where(KnowledgeArticle.workspace_id == workspace_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return 0
    for index, template in enumerate(DEFAULT_ARTICLES):
        db.add(
            KnowledgeArticle(
                workspace_id=workspace_id,
                slug=slugify(template["title"]),
                title=template["title"],
                summary=template.get("summary"),
                body=template["body"],
                section=template["section"],
                locale="en",
                position=index,
                is_active=True,
            )
        )
    return len(DEFAULT_ARTICLES)
