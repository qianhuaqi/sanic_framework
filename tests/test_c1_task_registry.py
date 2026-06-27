import asyncio

import pytest

from lingshu.system.execution import RequestExecutionContext, bind_execution_context
from lingshu.system.policy import CompiledRoutePolicy
from lingshu.system.tasks import TaskRegistry


def _context():
    return RequestExecutionContext(
        request_id="rid-task",
        trace_id="trace-task",
        route_policy=CompiledRoutePolicy(
            route_name="tasks.probe",
            public=True,
            auth_required=False,
            maintenance_check=True,
            timeout=5.0,
            body_limit=None,
            audit_level="none",
        ),
        deadline=999.0,
        lifecycle_state="ready",
    )


def test_task_registry_holds_strong_reference_and_removes_completed_tasks():
    async def scenario():
        registry = TaskRegistry()
        gate = asyncio.Event()

        async def job():
            await gate.wait()
            return "done"

        task_id = registry.spawn(job(), name="job", owner="application")
        assert len(registry.list()) == 1
        gate.set()
        await registry.shutdown_and_wait(timeout=1.0)
        assert registry.list() == []
        assert registry.get_result(task_id) == "done"

    asyncio.run(scenario())


def test_task_registry_consumes_task_exceptions():
    async def scenario():
        registry = TaskRegistry()

        async def job():
            raise RuntimeError("boom")

        task_id = registry.spawn(job(), name="boom", owner="application")
        await registry.shutdown_and_wait(timeout=1.0)

        record = registry.get_record(task_id)
        assert record.exception is not None
        assert "boom" in str(record.exception)
        assert registry.list() == []

    asyncio.run(scenario())


def test_task_registry_cancel_all_awaits_cancellation():
    async def scenario():
        registry = TaskRegistry()
        cleaned = asyncio.Event()

        async def job():
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()

        registry.spawn(job(), name="cancel-me", owner="application")
        await registry.cancel_all(reason="manual")
        assert cleaned.is_set()
        assert registry.list() == []

    asyncio.run(scenario())


def test_task_registry_captures_safe_context_snapshot_without_raw_request():
    async def scenario():
        registry = TaskRegistry()

        async def job():
            return "ok"

        with bind_execution_context(_context()):
            task_id = registry.spawn(job(), name="snapshot", owner="request")
        await registry.shutdown_and_wait(timeout=1.0)

        record = registry.get_record(task_id)
        assert record.request_id == "rid-task"
        assert record.operation_id is None
        assert record.raw_request is None

    asyncio.run(scenario())


def test_task_registry_rejects_missing_owner():
    registry = TaskRegistry()

    async def job():
        return None

    with pytest.raises(ValueError, match="owner"):
        registry.spawn(job(), name="bad", owner="")


def test_task_result_string_is_truncated():
    async def scenario():
        registry = TaskRegistry()
        big_string = "x" * 10000

        async def job():
            return big_string

        task_id = registry.spawn(job(), name="big", owner="application", scope="application")
        await registry.shutdown_and_wait(timeout=1.0)

        record = registry.get_record(task_id)
        assert isinstance(record.result, str)
        assert len(record.result) < 10000
        assert "truncated" in record.result

    asyncio.run(scenario())


def test_task_result_large_object_not_retained():
    async def scenario():
        registry = TaskRegistry()

        class BigObject:
            pass

        async def job():
            return BigObject()

        task_id = registry.spawn(job(), name="big-obj", owner="application", scope="application")
        await registry.shutdown_and_wait(timeout=1.0)

        record = registry.get_record(task_id)
        assert isinstance(record.result, str)
        assert "BigObject" in record.result

    asyncio.run(scenario())


def test_task_exception_sensitive_data_is_redacted():
    async def scenario():
        registry = TaskRegistry()

        async def job():
            raise RuntimeError("token=abc123 password=secret456 api_key=mykey789")

        task_id = registry.spawn(job(), name="leak", owner="application", scope="application")
        await registry.shutdown_and_wait(timeout=1.0)

        record = registry.get_record(task_id)
        assert record.exception_type == "RuntimeError"
        assert "abc123" not in record.exception_message
        assert "secret456" not in record.exception_message
        assert "mykey789" not in record.exception_message
        assert "***" in record.exception_message

    asyncio.run(scenario())


def test_task_exception_object_not_retained():
    async def scenario():
        registry = TaskRegistry()

        original_exc = RuntimeError("boom")

        async def job():
            raise original_exc

        task_id = registry.spawn(job(), name="exc-ref", owner="application", scope="application")
        await registry.shutdown_and_wait(timeout=1.0)

        record = registry.get_record(task_id)
        assert record.exception_type == "RuntimeError"
        assert "boom" in record.exception_message

    asyncio.run(scenario())


def test_task_record_captures_execution_id():
    async def scenario():
        registry = TaskRegistry()

        async def job():
            await asyncio.Event().wait()

        with bind_execution_context(_context()):
            task_id = registry.spawn(job(), name="exec-test", owner="request", scope="request")

        record = registry.get_record(task_id)
        assert record.execution_id is not None
        assert record.execution_id != ""

        await registry.cancel_all()
        await asyncio.sleep(0.01)

    asyncio.run(scenario())
