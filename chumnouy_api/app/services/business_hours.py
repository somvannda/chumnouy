"""Business-hours scheduling.

A workspace can define working hours (per weekday, in a timezone). SLA due dates
are then computed by adding working minutes, skipping nights and non-working
days. ``add_business_minutes`` is pure so it is easy to test.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DEFAULT_SCHEDULE: dict[str, list[str]] = {day: ["09:00", "17:00"] for day in WEEKDAYS[:5]}


def _minutes_of_day(value: str) -> int | None:
    try:
        hours, minutes = str(value).split(":")
        return int(hours) * 60 + int(minutes)
    except (ValueError, AttributeError):
        return None


def parse_schedule(days: dict | None) -> dict[int, tuple[int, int]]:
    """Turn ``{"mon": ["09:00", "17:00"]}`` into ``{0: (540, 1020)}``."""
    schedule: dict[int, tuple[int, int]] = {}
    for index, name in enumerate(WEEKDAYS):
        value = (days or {}).get(name)
        if not value or len(value) != 2:
            continue
        start, end = _minutes_of_day(value[0]), _minutes_of_day(value[1])
        if start is not None and end is not None and end > start:
            schedule[index] = (start, end)
    return schedule


def zone(name: str | None):
    if name:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return timezone.utc


def add_business_minutes(
    start: datetime, minutes: int, schedule: dict[int, tuple[int, int]], tz: str | None
) -> datetime:
    """Return ``start`` + ``minutes`` working minutes, skipping closed time."""
    if minutes <= 0 or not schedule:
        return start + timedelta(minutes=max(0, minutes))
    zoneinfo = zone(tz)
    current = start.astimezone(zoneinfo)
    remaining = float(minutes)
    for _ in range(2000):  # safety bound (~5 years of weekdays)
        day = schedule.get(current.weekday())
        midnight = current.replace(hour=0, minute=0, second=0, microsecond=0)
        if day is None:
            current = midnight + timedelta(days=1)
            continue
        day_start = midnight + timedelta(minutes=day[0])
        day_end = midnight + timedelta(minutes=day[1])
        if current < day_start:
            current = day_start
        if current >= day_end:
            current = midnight + timedelta(days=1)
            continue
        available = (day_end - current).total_seconds() / 60
        if remaining <= available:
            return current + timedelta(minutes=remaining)
        remaining -= available
        current = midnight + timedelta(days=1)
    return current
