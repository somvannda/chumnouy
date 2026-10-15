"""Business hours: the scheduling helper and its effect on SLA due dates."""
from datetime import datetime, timezone

import pytest

from app.services import business_hours as bh

WEEKDAYS_9_5 = {day: ["09:00", "17:00"] for day in ("mon", "tue", "wed", "thu", "fri")}


def test_parse_schedule():
    schedule = bh.parse_schedule(WEEKDAYS_9_5)
    assert schedule[0] == (540, 1020)
    assert 5 not in schedule  # saturday closed


def test_add_business_minutes_skips_the_weekend():
    # Friday 16:00 + 120 working minutes -> Monday 10:00.
    start = datetime(2026, 10, 16, 16, 0, tzinfo=timezone.utc)
    due = bh.add_business_minutes(start, 120, bh.parse_schedule(WEEKDAYS_9_5), "UTC")
    assert due == datetime(2026, 10, 19, 10, 0, tzinfo=timezone.utc)


def test_add_business_minutes_from_a_closed_day():
    # Saturday midday + 60 minutes -> Monday 10:00.
    start = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    due = bh.add_business_minutes(start, 60, bh.parse_schedule(WEEKDAYS_9_5), "UTC")
    assert due == datetime(2026, 10, 19, 10, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_sla_due_dates_respect_business_hours(client):
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": "bh@example.com", "password": "supersecret123", "name": "Owner", "workspace_name": "Acme"},
    )
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}
    integration = await client.post(
        "/api/v1/integrations",
        json={"name": "POS", "scopes": ["tickets:read", "tickets:write"]},
        headers=headers,
    )
    key = (
        await client.post(
            f"/api/v1/integrations/{integration.json()['id']}/keys", json={"name": "k"}, headers=headers
        )
    ).json()["key"]

    patched = await client.patch(
        "/api/v1/console/settings/business-hours",
        json={"enabled": True, "timezone": "UTC", "days": WEEKDAYS_9_5},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["business_hours"]["enabled"] is True

    created = await client.post(
        "/api/v1/tickets",
        json={"subject": "Hi", "message": "hello", "requester": {"external_id": "c1"}},
        headers={"X-Api-Key": key},
    )
    assert created.status_code == 201, created.text
    due = datetime.fromisoformat(created.json()["first_response_due_at"])
    assert due.weekday() < 5
    assert 9 <= due.hour < 17
