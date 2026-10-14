"""In-process sliding-window rate limiting.

A single API process today; if the API scales to multiple workers this should
move to shared storage (Redis or a DB counter) so the limit is global rather
than per worker (docs/architecture.md). Used to protect the public surface.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

_windows: dict[str, deque[float]] = defaultdict(deque)


def allow(key: str, *, limit: int, window_seconds: int = 60) -> bool:
    """Return True and record the call when under ``limit``, else False.

    A non-positive limit disables limiting (useful in tests).
    """
    if limit <= 0:
        return True
    now = time.monotonic()
    window = _windows[key]
    while window and now - window[0] > window_seconds:
        window.popleft()
    if len(window) >= limit:
        return False
    window.append(now)
    return True


def reset() -> None:
    """Clear all windows (tests)."""
    _windows.clear()
