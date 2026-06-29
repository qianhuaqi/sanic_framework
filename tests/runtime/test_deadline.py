from __future__ import annotations

import pytest
from lingshu.core.errors import DeadlineError
from lingshu.runtime import Deadline


class FakeClock:
    def __init__(self, now_ns: int = 0) -> None:
        self.value = now_ns

    def now_ns(self) -> int:
        return self.value

    def advance(self, duration_ns: int) -> None:
        self.value += duration_ns


def test_deadline_is_absolute_and_child_only_shortens() -> None:
    clock = FakeClock(100)
    parent = Deadline.after(1_000, clock)
    longer_child = parent.child(5_000, clock)
    shorter_child = parent.child(200, clock)
    assert parent.at_ns == 1_100
    assert longer_child.at_ns == parent.at_ns
    assert shorter_child.at_ns == 300
    clock.advance(150)
    assert shorter_child.remaining_ns(clock) == 50
    assert parent.remaining_ns(clock) == 850


def test_zero_budget_expires_immediately_and_raises_stable_error() -> None:
    clock = FakeClock(42)
    deadline = Deadline.after(0, clock)
    assert deadline.expired(clock)
    with pytest.raises(DeadlineError) as captured:
        deadline.check(clock)
    assert captured.value.code == "deadline.exceeded"


def test_deadline_rejects_negative_and_unbounded_construction() -> None:
    clock = FakeClock()
    with pytest.raises(ValueError):
        Deadline.after(-1, clock)
    with pytest.raises(ValueError):
        Deadline.combine(None, None)
