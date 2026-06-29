from __future__ import annotations

import asyncio

import pytest
from lingshu.core.errors import AdmissionError
from lingshu.core.time import SystemMonotonicClock
from lingshu.runtime import AdmissionOutcome, BoundedAdmission, Deadline


def future_deadline(seconds: float = 1.0) -> Deadline:
    clock = SystemMonotonicClock()
    return Deadline.after(int(seconds * 1_000_000_000), clock)


def test_immediate_lease_and_exactly_once_release() -> None:
    async def scenario() -> None:
        admission = BoundedAdmission(1, 1)
        lease = await admission.acquire()
        assert lease.outcome is AdmissionOutcome.IMMEDIATE
        assert admission.active == 1
        assert lease.release()
        assert not lease.release()
        assert admission.active == 0

    asyncio.run(scenario())


def test_fifo_waiters_receive_capacity_in_order() -> None:
    async def scenario() -> None:
        admission = BoundedAdmission(1, 2)
        first = await admission.acquire()
        order: list[str] = []

        async def acquire(name: str) -> None:
            lease = await admission.acquire(deadline=future_deadline())
            order.append(name)
            await asyncio.sleep(0)
            lease.release()

        second_task = asyncio.create_task(acquire("second"))
        await asyncio.sleep(0)
        third_task = asyncio.create_task(acquire("third"))
        await asyncio.sleep(0)
        assert admission.waiter_count == 2
        first.release()
        await asyncio.gather(second_task, third_task)
        assert order == ["second", "third"]
        assert admission.active == 0

    asyncio.run(scenario())


def test_waiter_bound_deadline_requirement_and_timeout() -> None:
    async def scenario() -> None:
        admission = BoundedAdmission(1, 1)
        lease = await admission.acquire()
        with pytest.raises(AdmissionError) as no_deadline:
            await admission.acquire()
        assert no_deadline.value.code == "admission.deadline_required"

        waiting = asyncio.create_task(admission.acquire(deadline=future_deadline()))
        await asyncio.sleep(0)
        with pytest.raises(AdmissionError) as full:
            await admission.acquire(deadline=future_deadline())
        assert full.value.code == "admission.capacity_exhausted"
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        assert admission.waiter_count == 0

        with pytest.raises(AdmissionError) as timeout:
            await admission.acquire(deadline=future_deadline(0.01))
        assert timeout.value.code == "admission.timeout"
        lease.release()

    asyncio.run(scenario())


def test_draining_and_unhealthy_reject_queued_and_new_work() -> None:
    async def scenario() -> None:
        admission = BoundedAdmission(1, 2)
        lease = await admission.acquire()
        queued = asyncio.create_task(admission.acquire(deadline=future_deadline()))
        await asyncio.sleep(0)
        admission.set_draining()
        with pytest.raises(AdmissionError) as queued_error:
            await queued
        assert queued_error.value.code == "admission.draining"
        with pytest.raises(AdmissionError) as draining:
            await admission.acquire()
        assert draining.value.code == "admission.draining"
        lease.release()

        admission.set_draining(False)
        admission.set_healthy(False)
        with pytest.raises(AdmissionError) as unhealthy:
            await admission.acquire()
        assert unhealthy.value.code == "admission.unhealthy"

    asyncio.run(scenario())


def test_async_context_releases_capacity() -> None:
    async def scenario() -> None:
        admission = BoundedAdmission(1, 0)
        async with await admission.acquire() as lease:
            assert not lease.released
            assert admission.active == 1
        assert lease.released
        assert admission.active == 0

    asyncio.run(scenario())
