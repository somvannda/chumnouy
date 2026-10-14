"""tickets: requesters, tickets, ticket_messages, ticket_events

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requesters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "external_id", name="uq_requester_workspace_external"),
    )
    op.create_index("ix_requesters_workspace_id", "requesters", ["workspace_id"])

    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(length=20), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("requester_id", sa.Uuid(), sa.ForeignKey("requesters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_integration_id", sa.Uuid(), sa.ForeignKey("integrations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assignee_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "reference", name="uq_ticket_workspace_reference"),
    )
    op.create_index("ix_tickets_workspace_id", "tickets", ["workspace_id"])
    op.create_index("ix_tickets_requester_id", "tickets", ["requester_id"])
    op.create_index("ix_tickets_assignee_user_id", "tickets", ["assignee_user_id"])
    op.create_index("ix_ticket_workspace_created", "tickets", ["workspace_id", "created_at"])
    op.create_index("ix_ticket_workspace_status", "tickets", ["workspace_id", "status"])

    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_type", sa.String(length=20), nullable=False, server_default="requester"),
        sa.Column("author_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("visibility", sa.String(length=20), nullable=False, server_default="public"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ticket_messages_ticket_id", "ticket_messages", ["ticket_id"])
    op.create_index("ix_ticket_messages_workspace_id", "ticket_messages", ["workspace_id"])
    op.create_index("ix_ticket_message_ticket_created", "ticket_messages", ["ticket_id", "created_at"])

    op.create_table(
        "ticket_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False, server_default="system"),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ticket_events_ticket_id", "ticket_events", ["ticket_id"])
    op.create_index("ix_ticket_events_workspace_id", "ticket_events", ["workspace_id"])
    op.create_index("ix_ticket_event_ticket_created", "ticket_events", ["ticket_id", "created_at"])


def downgrade() -> None:
    op.drop_table("ticket_events")
    op.drop_table("ticket_messages")
    op.drop_table("tickets")
    op.drop_table("requesters")
