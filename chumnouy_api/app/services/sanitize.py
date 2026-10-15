"""HTML sanitisation for rich message bodies.

A rich message is stored **sanitised**: a strict allowlist of tags and
attributes, no scripts, styles or event handlers. Anything else is stripped, so
the stored body is safe to render verbatim by any client.
"""
from __future__ import annotations

import bleach

ALLOWED_TAGS = [
    "p",
    "br",
    "hr",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "ul",
    "ol",
    "li",
    "blockquote",
    "code",
    "pre",
    "a",
    "h1",
    "h2",
    "h3",
    "h4",
]
ALLOWED_ATTRIBUTES = {"a": ["href", "title"]}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def sanitize_html(value: str) -> str:
    """Strip anything outside the allowlist from an HTML message body."""
    return bleach.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )


def render_body(value: str, body_format: str) -> str:
    """Return the body to store: sanitised when ``body_format`` is ``html``."""
    if body_format == "html":
        return sanitize_html(value)
    return value
