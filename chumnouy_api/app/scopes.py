"""Integration API key scopes.

A scope is a coarse capability granted to an integration key. Keys default to a
safe read-only set when none is given; ``tickets:write`` is never implicit.
"""

ALLOWED_SCOPES: frozenset[str] = frozenset(
    {
        "tickets:read",
        "tickets:write",
        "requesters:read",
        "requesters:write",
        "knowledge:read",
        "knowledge:write",
        "assistant:use",
        "webhooks:manage",
    }
)

DEFAULT_SCOPES: tuple[str, ...] = ("tickets:read",)


def normalise_scopes(scopes: list[str] | None) -> list[str]:
    """Keep only known scopes, de-duplicated and stably ordered."""
    if not scopes:
        return list(DEFAULT_SCOPES)
    seen: list[str] = []
    for scope in scopes:
        if scope in ALLOWED_SCOPES and scope not in seen:
            seen.append(scope)
    return seen or list(DEFAULT_SCOPES)
