"""Server-Sent Events formatting, shared by the assistant and chat streams."""
from __future__ import annotations

import json

MEDIA_TYPE = "text/event-stream"
# Stops proxies (nginx) from buffering the stream.
STREAM_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def format_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
