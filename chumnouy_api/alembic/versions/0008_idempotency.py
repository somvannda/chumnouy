"""idempotency: idempotency_keys

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("endpoint", sa.String(length=80), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "key", name="uq_idempotency_workspace_key"),
    )
    op.create_index("ix_idempotency_keys_workspace_id", "idempotency_keys", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("idempotency_keys")
