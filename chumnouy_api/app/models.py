"""SQLAlchemy models.

Tenancy (account -> workspace -> integration) and the ticket domain land in the
next build step (see docs/architecture.md §10). This module re-exports ``Base``
so Alembic has a metadata target today.
"""
from app.db import Base

__all__ = ["Base"]
