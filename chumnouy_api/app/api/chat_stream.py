"""Shared SSE response for chat sessions (requester and console streams).

The stream is deliberately **bounded**: it ends after ``timeout`` seconds and the
client reconnects. That keeps it dependency-free (no Redis pub/sub) and works the
same on one process or many.
"""
from __future__ import annotations

from datetime import datetime

from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatSession
from app.services import chat as svc
from app.sse import MEDIA_TYPE, STREAM_HEADERS, format_event

DEFAULT_TIMEOUT = 25.0
MAX_TIMEOUT = 60.0
MIN_TIMEOUT = 1.0
INTERVAL = 1.0


def stream_response(
    db: AsyncSession,
    session: ChatSession,
    *,
    after: datetime | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> StreamingResponse:
    bounded = max(MIN_TIMEOUT, min(timeout, MAX_TIMEOUT))

    async def events():
        async for event, data in svc.stream_events(
            db, session, after=after, timeout=bounded, interval=INTERVAL
        ):
            yield format_event(event, data)

    return StreamingResponse(events(), media_type=MEDIA_TYPE, headers=STREAM_HEADERS)
