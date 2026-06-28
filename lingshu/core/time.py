"""Clock contracts and strict UTC timestamp helpers."""

from __future__ import annotations

import re
import time as _time
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

_RFC3339_UTC_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})T(?P<time>\d{2}:\d{2}:\d{2})"
    r"(?P<fraction>\.\d{1,6})?Z$"
)


@runtime_checkable
class WallClock(Protocol):
    """Provide human-readable UTC wall time."""

    def now(self) -> datetime:
        """Return an aware UTC datetime."""


@runtime_checkable
class MonotonicClock(Protocol):
    """Provide process-local monotonic nanoseconds."""

    def now_ns(self) -> int:
        """Return a non-negative monotonic timestamp in nanoseconds."""


class SystemWallClock:
    """Read wall time from the system UTC clock."""

    __slots__ = ()

    def now(self) -> datetime:
        """Return the current aware UTC datetime."""

        return datetime.now(UTC)


class SystemMonotonicClock:
    """Read process-local monotonic nanoseconds from the system clock."""

    __slots__ = ()

    def now_ns(self) -> int:
        """Return the current monotonic timestamp in nanoseconds."""

        return _time.monotonic_ns()


def format_rfc3339_utc(value: datetime) -> str:
    """Format an aware datetime as canonical RFC3339 UTC with a trailing ``Z``.

    Zero microseconds are omitted. Non-zero microseconds are emitted with six digits so the
    representation is deterministic.

    Raises:
        ValueError: If ``value`` is naive.
    """

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("wall timestamp must be timezone-aware")

    utc_value = value.astimezone(UTC)
    timespec = "microseconds" if utc_value.microsecond else "seconds"
    return utc_value.isoformat(timespec=timespec).removesuffix("+00:00") + "Z"


def parse_rfc3339_utc(value: str) -> datetime:
    """Parse the strict LingShu RFC3339 UTC form.

    Only a trailing ``Z`` is accepted. Numeric offsets, whitespace, leap-second syntax, and
    fractional precision beyond microseconds are rejected.

    Raises:
        ValueError: If ``value`` is not a valid strict UTC timestamp.
    """

    if _RFC3339_UTC_PATTERN.fullmatch(value) is None:
        raise ValueError("timestamp must be strict RFC3339 UTC with a trailing Z")

    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("timestamp is not a valid calendar time") from exc

    return parsed.astimezone(UTC)


__all__ = (
    "MonotonicClock",
    "SystemMonotonicClock",
    "SystemWallClock",
    "WallClock",
    "format_rfc3339_utc",
    "parse_rfc3339_utc",
)
