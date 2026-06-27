import asyncio
from types import SimpleNamespace

import pytest

from lingshu import request
from lingshu.system.errors import NoRequestContextError
from lingshu.system.execution import (
    CancellationReason,
    RequestExecutionContext,
    bind_execution_context,
    current_deadline,
    current_execution_context,
    raise_if_cancelled,
    remaining_time,
)
from lingshu.system.policy import CompiledRoutePolicy


class FakeClock:
    def __init__(self, value=100.0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, amount):
        self.value += amount


def _policy(timeout=5.0):
    return CompiledRoutePolicy(
        route_name="demo.probe",
        public=True,
        auth_required=False,
        maintenance_check=True,
        timeout=timeout,
        body_limit=None,
        audit_level="none",
    )


def test_request_execution_context_exposes_deadline_and_resets():
    clock = FakeClock()
    context = RequestExecutionContext(
        request_id="rid-1",
        trace_id="trace-1",
        operation_id="op-1",
        route_policy=_policy(timeout=3.0),
        deadline=103.0,
        lifecycle_state="ready",
        monotonic=clock,
    )

    with bind_execution_context(context):
        assert current_execution_context() is context
        assert request.execution is context
        assert request.id == "rid-1"
        assert current_deadline() == 103.0
        assert remaining_time() == 3.0
        clock.advance(1.25)
        assert remaining_time() == pytest.approx(1.75)

    with pytest.raises(NoRequestContextError):
        current_execution_context()
    with pytest.raises(NoRequestContextError):
        _ = request.execution


def test_parent_deadline_constrains_child_context():
    clock = FakeClock()
    parent = RequestExecutionContext(
        request_id="parent",
        trace_id="trace-parent",
        route_policy=_policy(timeout=10.0),
        deadline=110.0,
        lifecycle_state="ready",
        monotonic=clock,
    )

    with bind_execution_context(parent):
        child = RequestExecutionContext.child(
            request_id="child",
            trace_id="trace-child",
            route_policy=_policy(timeout=30.0),
            timeout=30.0,
            lifecycle_state="ready",
            monotonic=clock,
        )

    assert child.deadline == 110.0


def test_cancel_reason_is_stable_and_cancelled_error_is_not_swallowed():
    context = RequestExecutionContext(
        request_id="rid-cancel",
        trace_id="trace-cancel",
        route_policy=_policy(),
        deadline=105.0,
        lifecycle_state="ready",
        monotonic=FakeClock(),
    )

    with bind_execution_context(context):
        current_execution_context().cancel(CancellationReason.MANUAL)
        with pytest.raises(asyncio.CancelledError):
            raise_if_cancelled()
        assert current_execution_context().cancel_reason == CancellationReason.MANUAL


def test_concurrent_execution_contexts_do_not_cross_contaminate_100_and_1000():
    async def run_many(total):
        ready = asyncio.Event()
        results = []

        async def worker(index):
            context = RequestExecutionContext(
                request_id=f"rid-{index}",
                trace_id=f"trace-{index}",
                route_policy=_policy(),
                deadline=105.0,
                lifecycle_state="ready",
                monotonic=FakeClock(),
            )
            with bind_execution_context(context):
                await ready.wait()
                results.append((index, request.id, current_execution_context().trace_id))

        tasks = [asyncio.create_task(worker(index)) for index in range(total)]
        await asyncio.sleep(0)
        ready.set()
        await asyncio.gather(*tasks)
        return results

    for total in (100, 1000):
        results = asyncio.run(run_many(total))
        assert sorted(results) == [(index, f"rid-{index}", f"trace-{index}") for index in range(total)]


def test_context_does_not_leak_into_background_task_after_scope_finishes():
    async def scenario():
        context = RequestExecutionContext(
            request_id="rid-bg",
            trace_id="trace-bg",
            route_policy=_policy(),
            deadline=105.0,
            lifecycle_state="ready",
            monotonic=FakeClock(),
        )
        gate = asyncio.Event()

        async def child():
            await gate.wait()
            with pytest.raises(NoRequestContextError):
                current_execution_context()

        with bind_execution_context(context):
            task = asyncio.create_task(child(), context=context.detached_context())
        gate.set()
        await task

    asyncio.run(scenario())
