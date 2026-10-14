"""assistant: assistant_conversations, assistant_messages, assistant_feedback

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("integration_id", sa.Uuid(), sa.ForeignKey("integrations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("locale", sa.String(length=5), nullable=False, server_default="en"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assistant_conversations_workspace_id", "assistant_conversations", ["workspace_id"])
    op.create_index("ix_assistant_conversation_workspace_updated", "assistant_conversations", ["workspace_id", "updated_at"])

    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("assistant_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assistant_messages_conversation_id", "assistant_messages", ["conversation_id"])
    op.create_index("ix_assistant_messages_workspace_id", "assistant_messages", ["workspace_id"])
    op.create_index("ix_assistant_message_conversation_created", "assistant_messages", ["conversation_id", "created_at"])

    op.create_table(
        "assistant_feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("assistant_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.String(length=10), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assistant_feedback_workspace_id", "assistant_feedback", ["workspace_id"])
    op.create_index("ix_assistant_feedback_message", "assistant_feedback", ["message_id"])


def downgrade() -> None:
    op.drop_table("assistant_feedback")
    op.drop_table("assistant_messages")
    op.drop_table("assistant_conversations")
