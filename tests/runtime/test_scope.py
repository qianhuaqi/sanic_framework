from __future__ import annotations

import asyncio

import pytest
from lingshu.core.errors import DeadlineError, LifecycleError
from lingshu.runtime import (
    CancellationReason,
    Deadline,
    Scope,
    ScopeCancelled,
    ScopeKind,
    ScopeState,
    current_scope,
)


class FakeClock:
    def __init__(self, now_ns: int = 0) -> None:
        self.value = now_ns

    def now_ns(self) -> int:
        return self.value

    def advance(self, duration_ns: int) -> None:
        self.value += duration_ns


def test_scope_hierarchy_and_deadline_inheritance() -> None:
    clock = FakeClock(100)
    app = Scope.application(clock=clock)
    connection = app.create_child(ScopeKind.CONNECTION)
    request = connection.create_child(ScopeKind.REQUEST, duration_ns=1_000)
    operation = request.create_child(ScopeKind.OPERATION, duration_ns=5_000)
    assert request.deadline is not None
    assert operation.deadline == request.deadline
    with pytest.raises(ValueError):
        app.create_child(ScopeKind.REQUEST, duration_ns=1)
    with pytest.raises(ValueError):
        connection.create_child(ScopeKind.OPERATION, duration_ns=1)


def test_current_scope_is_isolated_and_propagates_to_managed_tasks() -> None:
    async def scenario() -> None:
        app = Scope.application()
        seen: list[Scope | None] = []

        async def child() -> None:
            seen.append(current_scope())

        assert current_scope() is None
        async with app:
            assert current_scope() is app
            await app.spawn(child(), name="child")
        assert current_scope() is None
        assert seen == [app]

    asyncio.run(scenario())


def test_parent_cancellation_propagates_reason_and_preserves_control_flow() -> None:
    async def scenario() -> None:
        clock = FakeClock()
        app = Scope.application(clock=clock)
        connection = app.create_child(ScopeKind.CONNECTION)
        request = connection.create_child(ScopeKind.REQUEST, duration_ns=1_000)
        operation = request.create_child(ScopeKind.OPERATION, duration_ns=500)
        assert request.cancel(CancellationReason.CLIENT_DISCONNECT)
        assert not request.cancel(CancellationReason.WORKER_STOPPING)
        state = operation.cancellation.state
        assert state is not None
        assert state.reason is CancellationReason.PARENT_CANCELLED
        assert state.origin_reason is CancellationReason.CLIENT_DISCONNECT
        caught_by_exception = False
        try:
            operation.cancellation.checkpoint()
        except Exception:
            caught_by_exception = True
        except ScopeCancelled as exc:
            assert exc.cancellation.origin_reason is CancellationReason.CLIENT_DISCONNECT
        assert not caught_by_exception
        await app.close()

    asyncio.run(scenario())


def test_close_cancels_managed_tasks_and_is_idempotent() -> None:
    async def scenario() -> None:
        app = Scope.application(cleanup_budget_ns=1_000_000_000)
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def worker() -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        app.spawn(worker(), name="worker")
        await started.wait()
        first = await app.close()
        second = await app.close()
        assert first is second
        assert cancelled.is_set()
        assert first.incomplete_tasks == ()
        assert app.active_task_count == 0
        assert app.state is ScopeState.CLOSED
        late = worker()
        with pytest.raises(LifecycleError):
            app.spawn(late, name="late")
        late.close()

    asyncio.run(scenario())


def test_task_and_cleanup_failures_are_visible_and_cleanup_is_reverse_order() -> None:
    async def scenario() -> None:
        app = Scope.application()
        order: list[str] = []

        async def task() -> None:
            raise RuntimeError("task failed")

        async def cleanup_one() -> None:
            order.append("one")

        async def cleanup_two() -> None:
            order.append("two")
            raise ValueError("cleanup failed")

        app.register_cleanup("one", cleanup_one)
        app.register_cleanup("two", cleanup_two)
        app.spawn(task(), name="failing")
        await asyncio.sleep(0)
        report = await app.close()
        assert [failure.name for failure in report.task_failures] == ["failing"]
        assert [failure.name for failure in report.cleanup_failures] == ["two"]
        assert order == ["two", "one"]

    asyncio.run(scenario())


def test_cleanup_budget_times_out_without_hanging() -> None:
    async def scenario() -> None:
        app = Scope.application(cleanup_budget_ns=5_000_000)

        async def slow_cleanup() -> None:
            await asyncio.sleep(1)

        app.register_cleanup("slow", slow_cleanup)
        report = await app.close()
        assert report.timed_out
        assert app.state is ScopeState.CLOSED

    asyncio.run(scenario())


def test_checkpoint_marks_deadline_cancellation() -> None:
    clock = FakeClock()
    app = Scope.application(clock=clock)
    connection = app.create_child(ScopeKind.CONNECTION)
    request = connection.create_child(
        ScopeKind.REQUEST, deadline=Deadline.after(10, clock)
    )
    clock.advance(10)
    with pytest.raises(DeadlineError):
        request.checkpoint()
    state = request.cancellation.state
    assert state is not None
    assert state.reason is CancellationReason.REQUEST_DEADLINE
