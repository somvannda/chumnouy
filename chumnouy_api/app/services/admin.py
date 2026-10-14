"""Platform-operator queries (the ``/api/admin`` router).

Cross-tenant by design: only a console user whose ``platform_role`` is
``admin``/``super_admin`` reaches these (see ``deps.get_platform_admin``). A
tenant API key can never authenticate here.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Account,
    Integration,
    KnowledgeArticle,
    Membership,
    Requester,
    Ticket,
    WebhookDelivery,
    Workspace,
)
from app.schemas import (
    AdminAccountRead,
    AdminUsageRead,
    AdminWorkspaceDetail,
    AdminWorkspaceSummary,
    AdminWorkspaceUpdate,
)

OPEN_STATUSES = ("open", "pending")


async def _scalar(db: AsyncSession, stmt) -> int:
    return int((await db.execute(stmt)).scalar() or 0)


async def list_accounts(db: AsyncSession) -> list[AdminAccountRead]:
    accounts = (await db.execute(select(Account).order_by(Account.created_at))).scalars().all()
    counts = dict(
        (
            await db.execute(
                select(Workspace.account_id, func.count(Workspace.id)).group_by(Workspace.account_id)
            )
        ).all()
    )
    return [
        AdminAccountRead(
            id=account.id,
            name=account.name,
            slug=account.slug,
            status=account.status,
            workspace_count=int(counts.get(account.id, 0)),
            created_at=account.created_at,
        )
        for account in accounts
    ]


async def _workspace_summary(
    db: AsyncSession, workspace: Workspace, ticket_count: int
) -> AdminWorkspaceSummary:
    return AdminWorkspaceSummary(
        id=workspace.id,
        account_id=workspace.account_id,
        name=workspace.name,
        slug=workspace.slug,
        is_active=workspace.is_active,
        ticket_count=ticket_count,
        created_at=workspace.created_at,
    )


async def list_workspaces(
    db: AsyncSession,
    *,
    q: str | None = None,
    active: bool | None = None,
    limit: int = 100,
) -> list[AdminWorkspaceSummary]:
    stmt = select(Workspace)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Workspace.name.ilike(like), Workspace.slug.ilike(like)))
    if active is not None:
        stmt = stmt.where(Workspace.is_active.is_(active))
    stmt = stmt.order_by(Workspace.created_at).limit(max(1, min(limit, 500)))
    workspaces = (await db.execute(stmt)).scalars().all()
    counts = dict(
        (
            await db.execute(
                select(Ticket.workspace_id, func.count(Ticket.id)).group_by(Ticket.workspace_id)
            )
        ).all()
    )
    return [
        await _workspace_summary(db, workspace, int(counts.get(workspace.id, 0)))
        for workspace in workspaces
    ]


async def get_workspace(db: AsyncSession, workspace_id: UUID) -> Workspace | None:
    return (
        await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ).scalar_one_or_none()


async def workspace_detail(db: AsyncSession, workspace: Workspace) -> AdminWorkspaceDetail:
    ticket_count = await _scalar(
        db, select(func.count(Ticket.id)).where(Ticket.workspace_id == workspace.id)
    )
    summary = await _workspace_summary(db, workspace, ticket_count)
    return AdminWorkspaceDetail(
        **summary.model_dump(),
        member_count=await _scalar(
            db, select(func.count(Membership.id)).where(Membership.workspace_id == workspace.id)
        ),
        integration_count=await _scalar(
            db, select(func.count(Integration.id)).where(Integration.workspace_id == workspace.id)
        ),
        knowledge_article_count=await _scalar(
            db,
            select(func.count(KnowledgeArticle.id)).where(
                KnowledgeArticle.workspace_id == workspace.id
            ),
        ),
        quota=dict((workspace.settings or {}).get("quota") or {}),
    )


async def update_workspace(
    db: AsyncSession, workspace: Workspace, payload: AdminWorkspaceUpdate
) -> AdminWorkspaceDetail:
    if payload.is_active is not None:
        workspace.is_active = payload.is_active
    if payload.quota is not None:
        settings = dict(workspace.settings or {})
        settings["quota"] = payload.quota
        workspace.settings = settings
    await db.commit()
    await db.refresh(workspace)
    return await workspace_detail(db, workspace)


async def usage_summary(db: AsyncSession) -> AdminUsageRead:
    return AdminUsageRead(
        accounts=await _scalar(db, select(func.count(Account.id))),
        workspaces=await _scalar(db, select(func.count(Workspace.id))),
        active_workspaces=await _scalar(
            db, select(func.count(Workspace.id)).where(Workspace.is_active.is_(True))
        ),
        tickets=await _scalar(db, select(func.count(Ticket.id))),
        open_tickets=await _scalar(
            db, select(func.count(Ticket.id)).where(Ticket.status.in_(OPEN_STATUSES))
        ),
        requesters=await _scalar(db, select(func.count(Requester.id))),
        integrations=await _scalar(db, select(func.count(Integration.id))),
        knowledge_articles=await _scalar(db, select(func.count(KnowledgeArticle.id))),
        webhook_deliveries=await _scalar(db, select(func.count(WebhookDelivery.id))),
    )
