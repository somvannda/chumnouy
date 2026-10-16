"""Sign-in access control: an optional per-workspace IP allowlist.

Stored under ``workspace.settings["security"]["ip_allowlist"]`` — a list of IPs or
CIDR blocks. When the list is empty (the default) sign-in is unrestricted. The
client address comes from ``X-Forwarded-For`` (first hop) when a proxy sets it,
else the socket peer; when neither is available the check passes, so a
misconfigured proxy cannot lock everyone out.
"""
from __future__ import annotations

import ipaddress

from fastapi import Request

from app.models import Workspace


def ip_allowlist(workspace: Workspace) -> list[str]:
    security = (workspace.settings or {}).get("security") or {}
    raw = security.get("ip_allowlist")
    return [str(entry).strip() for entry in raw if str(entry).strip()] if isinstance(raw, list) else []


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else None


def _matches(network, address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    return parsed in network


def is_allowed(workspace: Workspace, address: str | None) -> bool:
    """``True`` when the address may sign in (empty list, or no address, allows)."""
    allowlist = ip_allowlist(workspace)
    if not allowlist or not address:
        return True
    for entry in allowlist:
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            continue
        if _matches(network, address):
            return True
    return False
