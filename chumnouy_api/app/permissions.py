"""Workspace roles and their permissions.

A membership role is a coarse capability set. Console users (JWT) are checked
against this; API keys are checked against their scopes instead. Roles:
``owner`` > ``admin`` > ``team_lead`` > ``agent`` > ``viewer``.
"""
from __future__ import annotations

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": frozenset({"*"}),
    "admin": frozenset(
        {"teams:manage", "tickets:manage", "settings:manage", "members:manage", "keys:manage"}
    ),
    "team_lead": frozenset({"tickets:manage", "teams:manage"}),
    "agent": frozenset({"tickets:manage"}),
    "viewer": frozenset(),
}

ROLES = tuple(ROLE_PERMISSIONS)


def has_permission(role: str | None, action: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(role or "", frozenset())
    return "*" in permissions or action in permissions
