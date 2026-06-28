from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from lingshu.core import (
    SystemMonotonicClock,
    SystemWallClock,
    format_rfc3339_utc,
    parse_rfc3339_utc,
)


def test_system_wall_clock_returns_aware_utc() -> None:
    value = SystemWallClock().now()
    assert value.tzinfo is UTC
    assert value.utcoffset() == timedelta(0)


def test_system_monotonic_clock_returns_non_negative_nanoseconds() -> None:
    clock = SystemMonotonicClock()
    first = clock.now_ns()
    second = clock.now_ns()
    assert isinstance(first, int)
    assert first >= 0
    assert second >= first


def test_rfc3339_format_is_canonical_utc() -> None:
    offset = timezone(timedelta(hours=8))
    value = datetime(2026, 6, 28, 17, 30, 45, 123456, tzinfo=offset)
    assert format_rfc3339_utc(value) == "2026-06-28T09:30:45.123456Z"
    assert format_rfc3339_utc(datetime(2026, 6, 28, 9, 30, 45, tzinfo=UTC)) == (
        "2026-06-28T09:30:45Z"
    )


def test_rfc3339_parse_accepts_only_strict_utc() -> None:
    assert parse_rfc3339_utc("2026-06-28T09:30:45.1Z") == datetime(
        2026, 6, 28, 9, 30, 45, 100000, tzinfo=UTC
    )
    for invalid in (
        "2026-06-28 09:30:45Z",
        "2026-06-28T09:30:45+00:00",
        "2026-06-28T09:30:45.1234567Z",
        "2026-06-28T09:30:60Z",
        " 2026-06-28T09:30:45Z",
    ):
        with pytest.raises(ValueError):
            parse_rfc3339_utc(invalid)


def test_rfc3339_format_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        format_rfc3339_utc(datetime(2026, 6, 28, 9, 30, 45))
