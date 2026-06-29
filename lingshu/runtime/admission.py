"""Bounded FIFO admission with explicit rejection outcomes."""

from __future__ import annotations

import asyncio
from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum

from lingshu.core.errors import AdmissionError, FatalScope
from lingshu.core.time import MonotonicClock, SystemMonotonicClock
from lingshu.runtime.deadline import Deadline


class AdmissionOutcome(StrEnum):
    """Successful admission path."""

    IMMEDIATE = "immediate"
    WAITED = "waited"


@dataclass(slots=True)
class _Waiter:
    future: asyncio.Future[None]
    enqueued_ns: int


class AdmissionLease:
    """Exactly-once capacity lease."""

    __slots__ = ("_admission", "_released", "outcome", "waited_ns")

    def __init__(self, admission: BoundedAdmission, *, outcome: AdmissionOutcome, waited_ns: int) -> None:
        self._admission = admission
        self._released = False
        self.outcome = outcome
        self.waited_ns = waited_ns

    @property
    def released(self) -> bool:
        return self._released

    def release(self) -> bool:
        """Release once and return whether this call changed capacity."""
        if self._released:
            return False
        self._released = True
        self._admission._release()
        return True

    async def __aenter__(self) -> AdmissionLease:
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: object | None) -> None:
        del exc_type, exc, traceback
        self.release()


class BoundedAdmission:
    """Event-loop-local bounded active and waiter capacity."""

    def __init__(self, limit: int, max_waiters: int, *, clock: MonotonicClock | None = None) -> None:
        if limit <= 0:
            raise ValueError("admission limit must be positive")
        if max_waiters < 0:
            raise ValueError("max_waiters must be non-negative")
        self.limit = limit
        self.max_waiters = max_waiters
        self.clock = clock or SystemMonotonicClock()
        self.active = 0
        self._waiters: deque[_Waiter] = deque()
        self.draining = False
        self.healthy = True

    @property
    def waiter_count(self) -> int:
        return len(self._waiters)

    async def acquire(self, *, deadline: Deadline | None = None) -> AdmissionLease:
        """Acquire immediately or wait in the bounded FIFO queue."""
        self._ensure_available_state()
        if deadline is not None and deadline.expired(self.clock):
            raise _admission_error("admission.timeout", "Admission wait deadline was exceeded.", retryable=True)
        if self.active < self.limit and not self._waiters:
            self.active += 1
            return AdmissionLease(self, outcome=AdmissionOutcome.IMMEDIATE, waited_ns=0)
        if self.max_waiters == 0 or len(self._waiters) >= self.max_waiters:
            raise _admission_error("admission.capacity_exhausted", "Admission capacity is exhausted.", retryable=True)
        if deadline is None:
            raise _admission_error("admission.deadline_required", "Queued admission requires a finite Deadline.")

        loop = asyncio.get_running_loop()
        waiter = _Waiter(loop.create_future(), self.clock.now_ns())
        self._waiters.append(waiter)
        try:
            remaining = deadline.remaining_seconds(self.clock)
            if remaining <= 0:
                raise TimeoutError
            async with asyncio.timeout(remaining):
                await waiter.future
        except TimeoutError as exc:
            granted = self._waiter_was_granted(waiter)
            self._remove_waiter(waiter)
            if granted:
                self._release()
            raise _admission_error("admission.timeout", "Admission wait deadline was exceeded.", retryable=True) from exc
        except asyncio.CancelledError:
            granted = self._waiter_was_granted(waiter)
            self._remove_waiter(waiter)
            if granted:
                self._release()
            raise

        return AdmissionLease(self, outcome=AdmissionOutcome.WAITED, waited_ns=max(0, self.clock.now_ns() - waiter.enqueued_ns))

    def set_draining(self, draining: bool = True) -> None:
        """Reject new and queued work while draining."""
        self.draining = draining
        if draining:
            self._reject_waiters(_admission_error("admission.draining", "The service is draining and is not accepting new work.", retryable=True))

    def set_healthy(self, healthy: bool) -> None:
        """Reject new and queued work when the dependency/service is unhealthy."""
        self.healthy = healthy
        if not healthy:
            self._reject_waiters(_admission_error("admission.unhealthy", "Admission dependency is unhealthy.", retryable=True))

    def _ensure_available_state(self) -> None:
        if self.draining:
            raise _admission_error("admission.draining", "The service is draining and is not accepting new work.", retryable=True)
        if not self.healthy:
            raise _admission_error("admission.unhealthy", "Admission dependency is unhealthy.", retryable=True)

    def _release(self) -> None:
        if self.active <= 0:
            raise RuntimeError("admission release without active capacity")
        self.active -= 1
        while self._waiters:
            waiter = self._waiters.popleft()
            if waiter.future.done():
                continue
            self.active += 1
            waiter.future.set_result(None)
            break

    def _remove_waiter(self, waiter: _Waiter) -> None:
        with suppress(ValueError):
            self._waiters.remove(waiter)

    def _waiter_was_granted(self, waiter: _Waiter) -> bool:
        return waiter.future.done() and not waiter.future.cancelled() and waiter.future.exception() is None and waiter not in self._waiters

    def _reject_waiters(self, error: AdmissionError) -> None:
        while self._waiters:
            waiter = self._waiters.popleft()
            if not waiter.future.done():
                waiter.future.set_exception(error)


def _admission_error(code: str, message: str, *, retryable: bool = False) -> AdmissionError:
    return AdmissionError(code, message, retryable=retryable, fatal_scope=FatalScope.REQUEST)


__all__ = ("AdmissionLease", "AdmissionOutcome", "BoundedAdmission")
