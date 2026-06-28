"""Absolute monotonic Deadline primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from lingshu.core.errors import DeadlineError, FatalScope
from lingshu.core.time import MonotonicClock


@dataclass(frozen=True, slots=True)
class Deadline:
    """An absolute process-local monotonic deadline in nanoseconds."""

    at_ns: int

    def __post_init__(self) -> None:
        if self.at_ns < 0:
            raise ValueError("deadline must be a non-negative monotonic timestamp")

    @classmethod
    def after(
        cls,
        duration_ns: int,
        clock: MonotonicClock,
        *,
        parent: Deadline | None = None,
    ) -> Self:
        """Create a deadline after ``duration_ns``, never later than ``parent``."""

        if duration_ns < 0:
            raise ValueError("deadline duration must be non-negative")
        candidate = cls(clock.now_ns() + duration_ns)
        return cls.combine(parent, candidate)

    @classmethod
    def combine(cls, parent: Deadline | None, requested: Deadline | None) -> Self:
        """Return the earliest finite deadline.

        At least one deadline is required so callers cannot accidentally create an unbounded
        request or operation budget.
        """

        if parent is None and requested is None:
            raise ValueError("at least one deadline is required")
        if parent is None:
            assert requested is not None
            return cls(requested.at_ns)
        if requested is None:
            return cls(parent.at_ns)
        return cls(min(parent.at_ns, requested.at_ns))

    def child(self, duration_ns: int, clock: MonotonicClock) -> Self:
        """Create a child budget that may only shorten this deadline."""

        return type(self).after(duration_ns, clock, parent=self)

    def remaining_ns(self, clock: MonotonicClock) -> int:
        """Return a clamped non-negative remaining budget."""

        return max(0, self.at_ns - clock.now_ns())

    def remaining_seconds(self, clock: MonotonicClock) -> float:
        """Return the remaining budget as seconds for asyncio timeout APIs."""

        return self.remaining_ns(clock) / 1_000_000_000

    def expired(self, clock: MonotonicClock) -> bool:
        """Return whether no budget remains."""

        return clock.now_ns() >= self.at_ns

    def check(self, clock: MonotonicClock) -> None:
        """Raise the stable framework DeadlineError when expired."""

        if self.expired(clock):
            raise deadline_exceeded_error()


def deadline_exceeded_error() -> DeadlineError:
    """Construct the stable safe Deadline exhaustion error."""

    return DeadlineError(
        "deadline.exceeded",
        "The operation deadline was exceeded.",
        retryable=True,
        fatal_scope=FatalScope.OPERATION,
    )


__all__ = ("Deadline", "deadline_exceeded_error")
