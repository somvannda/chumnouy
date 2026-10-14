"""The background worker loop drains both outboxes and stops cleanly."""
import asyncio

import pytest

from app import db as app_db
from app.config import settings
from app.services import notifyr as notifyr_svc
from app.services import webhooks as webhook_svc

pytestmark = pytest.mark.asyncio


async def test_worker_drains_both_outboxes_and_stops(session_factory, monkeypatch):
    calls: list[str] = []

    async def fake_webhooks(db, *, limit=50, client=None):
        calls.append("webhooks")
        return 0

    async def fake_notifyr(db, *, limit=50, client=None):
        calls.append("notifyr")
        return 0

    # The worker opens its own sessions; point it at an in-memory factory.
    monkeypatch.setattr(app_db, "SessionLocal", session_factory)
    monkeypatch.setattr(webhook_svc, "process_due", fake_webhooks)
    monkeypatch.setattr(notifyr_svc, "process_due", fake_notifyr)
    monkeypatch.setattr(settings, "webhook_worker_interval_seconds", 1)

    stop = asyncio.Event()
    task = asyncio.create_task(webhook_svc.run_worker(stop))
    await asyncio.sleep(0.2)
    stop.set()
    await asyncio.wait_for(task, timeout=5)

    assert "webhooks" in calls
    assert "notifyr" in calls


async def test_worker_survives_a_failing_iteration(session_factory, monkeypatch):
    calls: list[str] = []

    async def boom(db, *, limit=50, client=None):
        calls.append("boom")
        raise RuntimeError("transient")

    async def fake_notifyr(db, *, limit=50, client=None):
        return 0

    monkeypatch.setattr(app_db, "SessionLocal", session_factory)
    monkeypatch.setattr(webhook_svc, "process_due", boom)
    monkeypatch.setattr(notifyr_svc, "process_due", fake_notifyr)
    monkeypatch.setattr(settings, "webhook_worker_interval_seconds", 1)

    stop = asyncio.Event()
    task = asyncio.create_task(webhook_svc.run_worker(stop))
    await asyncio.sleep(0.2)
    stop.set()
    await asyncio.wait_for(task, timeout=5)

    # The failure was swallowed; the loop still exited cleanly.
    assert calls and task.done() and task.exception() is None
