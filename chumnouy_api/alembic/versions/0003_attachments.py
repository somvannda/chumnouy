"""attachments: ticket_attachments

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticket_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("ticket_messages.id", ondelete="CASCADE"), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ticket_attachments_workspace_id", "ticket_attachments", ["workspace_id"])
    op.create_index("ix_ticket_attachment_workspace_sha", "ticket_attachments", ["workspace_id", "sha256"])
    op.create_index("ix_ticket_attachment_ticket_created", "ticket_attachments", ["ticket_id", "created_at"])
    op.create_index("ix_ticket_attachment_message_id", "ticket_attachments", ["message_id"])


def downgrade() -> None:
    op.drop_table("ticket_attachments")
