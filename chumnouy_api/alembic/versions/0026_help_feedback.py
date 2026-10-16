"""help_article_feedback

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "help_article_feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "article_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("helpful", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_help_article_feedback_workspace_id", "help_article_feedback", ["workspace_id"])
    op.create_index("ix_help_article_feedback_article_id", "help_article_feedback", ["article_id"])
    op.create_index(
        "ix_help_feedback_article_created", "help_article_feedback", ["article_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("help_article_feedback")
