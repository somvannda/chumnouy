"""search: Postgres full-text indexes

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-15

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# GIN expression indexes make the ILIKE search fast on Postgres. They are
# Postgres-only, so the migration is a no-op elsewhere (tests build the schema
# from the models, not from migrations).
_INDEXES = (
    ("ix_ticket_subject_fts", "tickets", "to_tsvector('simple', subject)"),
    ("ix_ticket_message_body_fts", "ticket_messages", "to_tsvector('simple', body)"),
    (
        "ix_knowledge_article_fts",
        "knowledge_articles",
        "to_tsvector('simple', title || ' ' || body)",
    ),
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for name, table, expression in _INDEXES:
        op.execute(f"CREATE INDEX {name} ON {table} USING gin ({expression})")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for name, _table, _expression in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
