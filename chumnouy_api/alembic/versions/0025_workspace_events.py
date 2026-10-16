"""workspace_events: account/workspace-level audit trail

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=60), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column(
            "actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspace_events_workspace_id", "workspace_events", ["workspace_id"])
    op.create_index(
        "ix_workspace_event_workspace_created", "workspace_events", ["workspace_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("workspace_events")
