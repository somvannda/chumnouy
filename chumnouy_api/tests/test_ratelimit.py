"""Public-surface rate limiting (in-process sliding window, per client IP)."""
import pytest

from app.config import settings
from app.services import ratelimit

pytestmark = pytest.mark.asyncio


async def test_public_surface_is_throttled(client, monkeypatch):
    ratelimit.reset()
    monkeypatch.setattr(settings, "public_rate_limit_per_minute", 2)
    try:
        first = await client.get("/api/v1/public/tickets")
        second = await client.get("/api/v1/public/tickets")
        third = await client.get("/api/v1/public/tickets")

        assert first.status_code != 429
        assert second.status_code != 429
        assert third.status_code == 429
        assert third.headers.get("retry-after") == "60"
    finally:
        ratelimit.reset()


async def test_tenant_surface_is_not_affected(client, monkeypatch):
    ratelimit.reset()
    monkeypatch.setattr(settings, "public_rate_limit_per_minute", 1)
    try:
        for _ in range(3):
            assert (await client.get("/api/v1/health")).status_code == 200
    finally:
        ratelimit.reset()
