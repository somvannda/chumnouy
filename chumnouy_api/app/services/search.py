"""Workspace-scoped search across tickets, messages and knowledge articles.

A portable ``ILIKE`` search for v1; migration ``0011_search`` adds Postgres GIN
expression indexes so it stays fast as volume grows. Everything is scoped to the
caller's workspace.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeArticle, Ticket, TicketMessage
from app.schemas import SearchResult, SearchResults

SNIPPET_CHARS = 160
DEFAULT_LIMIT = 30
MAX_LIMIT = 100
SEARCH_TYPES = ("ticket", "message", "article")


def _snippet(text: str, query: str) -> str:
    """A short window of ``text`` around the first match, else the head."""
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    index = lowered.find(query.lower())
    if index == -1:
        return cleaned[:SNIPPET_CHARS] + ("…" if len(cleaned) > SNIPPET_CHARS else "")
    start = max(0, index - SNIPPET_CHARS // 3)
    end = min(len(cleaned), start + SNIPPET_CHARS)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(cleaned) else ""
    return f"{prefix}{cleaned[start:end]}{suffix}"


async def search(
    db: AsyncSession,
    workspace_id: UUID,
    *,
    q: str,
    types: list[str] | None = None,
    limit: int = DEFAULT_LIMIT,
) -> SearchResults:
    query = (q or "").strip()
    if not query:
        return SearchResults(query=q or "", results=[])
    wanted = [t for t in (types or SEARCH_TYPES) if t in SEARCH_TYPES] or list(SEARCH_TYPES)
    like = f"%{query}%"
    capped = max(1, min(limit, MAX_LIMIT))
    results: list[SearchResult] = []

    if "ticket" in wanted:
        rows = (
            await db.execute(
                select(Ticket)
                .where(Ticket.workspace_id == workspace_id, Ticket.subject.ilike(like))
                .order_by(Ticket.created_at.desc())
                .limit(capped)
            )
        ).scalars().all()
        for ticket in rows:
            results.append(
                SearchResult(
                    type="ticket",
                    id=ticket.id,
                    title=ticket.subject,
                    snippet=_snippet(ticket.subject, query),
                    ticket_id=ticket.id,
                    reference=ticket.reference,
                    created_at=ticket.created_at,
                )
            )

    if "message" in wanted:
        rows = (
            await db.execute(
                select(TicketMessage, Ticket)
                .join(Ticket, Ticket.id == TicketMessage.ticket_id)
                .where(TicketMessage.workspace_id == workspace_id, TicketMessage.body.ilike(like))
                .order_by(TicketMessage.created_at.desc())
                .limit(capped)
            )
        ).all()
        for message, ticket in rows:
            results.append(
                SearchResult(
                    type="message",
                    id=message.id,
                    title=ticket.subject,
                    snippet=_snippet(message.body, query),
                    ticket_id=ticket.id,
                    reference=ticket.reference,
                    created_at=message.created_at,
                )
            )

    if "article" in wanted:
        rows = (
            await db.execute(
                select(KnowledgeArticle)
                .where(
                    KnowledgeArticle.workspace_id == workspace_id,
                    KnowledgeArticle.is_active.is_(True),
                    or_(
                        KnowledgeArticle.title.ilike(like),
                        KnowledgeArticle.body.ilike(like),
                    ),
                )
                .order_by(KnowledgeArticle.position, KnowledgeArticle.created_at)
                .limit(capped)
            )
        ).scalars().all()
        for article in rows:
            results.append(
                SearchResult(
                    type="article",
                    id=article.id,
                    title=article.title,
                    snippet=_snippet(article.body, query),
                    created_at=article.created_at,
                )
            )

    return SearchResults(query=query, results=results[:capped])
