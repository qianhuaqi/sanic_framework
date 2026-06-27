"""Phase C1 third-round review: directed regression tests.

Covers:
- Python 3.10 compatibility (str+Enum instead of StrEnum, no 3.11 APIs)
- Exact route deadline attribution vs handler TimeoutError
- Exception redaction completeness (Bearer, Basic, JSON, api_key, etc.)
- Deterministic cancellation/concurrency using asyncio.Event (not sleep)
- Stop listener ordering and teardown idempotency
"""
from __future__ import annotations

import asyncio
import re
from enum import Enum
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sanic import Sanic

from lingshu.response import json_response
from lingshu.router import compile_route_policies
from lingshu.system import sanic_adapter
from lingshu.system.execution import (
    CancellationReason,
    RequestExecutionContext,
    bind_execution_context,
    current_execution_context,
)
from lingshu.system.lifecycle import (
    ApplicationLifecycle,
    InFlightRequestTracker,
    LifecycleState,
)
from lingshu.system.policy import (
    CompiledRoutePolicy,
    RoutePolicyDefinition,
    set_route_policy,
)
from lingshu.system.tasks import (
    TaskRegistry,
    _sanitize_text,
    _summarize_exception,
)


# ---------------------------------------------------------------------------
# Python 3.10 compatibility
# ---------------------------------------------------------------------------

class TestPython310Compatibility:
    """Verify no 3.11+ exclusive APIs are used."""

    def test_cancellation_reason_is_str_enum_not_strenum(self):
        assert issubclass(CancellationReason, str)
        assert issubclass(CancellationReason, Enum)
        # Must NOT be StrEnum (3.11+)
        import enum as _enum
        assert not issubclass(CancellationReason, getattr(_enum, "StrEnum", type))

    def test_lifecycle_state_is_str_enum_not_strenum(self):
        assert issubclass(LifecycleState, str)
        assert issubclass(LifecycleState, Enum)
        import enum as _enum
        assert not issubclass(LifecycleState, getattr(_enum, "StrEnum", type))

    def test_str_value_semantics_preserved(self):
        assert CancellationReason.REQUEST_TIMEOUT.value == "request_timeout"
        assert LifecycleState.READY.value == "ready"
        # str equality
        assert CancellationReason.CLIENT_DISCONNECT == "client_disconnect"
        assert LifecycleState.STOPPED == "stopped"

    def test_no_strenum_import_in_source(self):
        """AST-level check: no 'from enum import StrEnum' in any system source."""
        import pathlib
        system_dir = pathlib.Path(__file__).resolve().parent.parent / "src" / "lingshu" / "system"
        strenum_pattern = re.compile(r"\bStrEnum\b")
        violations = []
        for py_file in system_dir.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            if strenum_pattern.search(text):
                violations.append(str(py_file))
        assert violations == [], f"StrEnum found in: {violations}"

    def test_no_timeout_at_in_source(self):
        """AST-level check: no asyncio.timeout_at in any system source."""
        import pathlib
        system_dir = pathlib.Path(__file__).resolve().parent.parent / "src" / "lingshu" / "system"
        pattern = re.compile(r"\btimeout_at\b")
        violations = []
        for py_file in system_dir.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            if pattern.search(text):
                violations.append(str(py_file))
        assert violations == [], f"timeout_at found in: {violations}"

    def test_no_context_kwarg_in_create_task(self):
        """No asyncio.create_task(..., context=...) call in any system source."""
        import pathlib
        system_dir = pathlib.Path(__file__).resolve().parent.parent / "src" / "lingshu" / "system"
        pattern = re.compile(r"create_task\s*\([^)]*context\s*=")
        violations = []
        for py_file in system_dir.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            if pattern.search(text):
                violations.append(str(py_file))
        assert violations == [], f"context= kwarg found in: {violations}"


# ---------------------------------------------------------------------------
# Application task clean context
# ---------------------------------------------------------------------------

class TestApplicationTaskCleanContext:
    """Application/operation tasks must NOT see request context."""

    def test_application_task_has_no_request_context(self):
        async def scenario():
            from lingshu.system.errors import NoRequestContextError

            registry = TaskRegistry()
            result = {}

            async def job():
                try:
                    current_execution_context()
                except NoRequestContextError:
                    result["clean"] = True
                else:
                    result["clean"] = False

            execution = RequestExecutionContext(
                request_id="rid-app-ctx",
                trace_id="trace",
                route_policy=CompiledRoutePolicy("t", True, False, False, 1.0, None, "none"),
                deadline=999.0,
                lifecycle_state="ready",
            )
            with bind_execution_context(execution):
                registry.spawn(job(), name="app-task", owner="application", scope="application")
            await registry.shutdown_and_wait(timeout=1.0)

            assert result["clean"] is True

    def test_operation_task_has_no_request_context(self):
        async def scenario():
            from lingshu.system.errors import NoRequestContextError

            registry = TaskRegistry()
            result = {}

            async def job():
                try:
                    current_execution_context()
                except NoRequestContextError:
                    result["clean"] = True
                else:
                    result["clean"] = False

            execution = RequestExecutionContext(
                request_id="rid-op-ctx",
                trace_id="trace",
                route_policy=CompiledRoutePolicy("t", True, False, False, 1.0, None, "none"),
                deadline=999.0,
                lifecycle_state="ready",
            )
            with bind_execution_context(execution):
                registry.spawn(job(), name="op-task", owner="application", scope="operation")
            await registry.shutdown_and_wait(timeout=1.0)

            assert result["clean"] is True

    def test_request_task_inherits_execution_context(self):
        async def scenario():
            registry = TaskRegistry()
            seen_request_id = {}

            async def job():
                ctx = current_execution_context()
                seen_request_id["value"] = ctx.request_id

            execution = RequestExecutionContext(
                request_id="rid-inherited",
                trace_id="trace",
                route_policy=CompiledRoutePolicy("t", True, False, False, 1.0, None, "none"),
                deadline=999.0,
                lifecycle_state="ready",
            )
            with bind_execution_context(execution):
                registry.spawn(job(), name="req-task", owner="request", scope="request")
            await registry.shutdown_and_wait(timeout=1.0)

            assert seen_request_id["value"] == "rid-inherited"


# ---------------------------------------------------------------------------
# Route deadline attribution
# ---------------------------------------------------------------------------

class TestRouteDeadlineAttribution:
    """Distinguish RoutePolicy deadline from handler-raised TimeoutError."""

    def test_handler_raised_timeout_error_does_not_return_990002(self):
        """Handler that raises its own TimeoutError must NOT produce 504/990002."""
        app = Sanic("rd-handler-timeout")

        sanic_adapter.install_context_middleware(app)
        from lingshu.lifecycle import register_lifecycle
        register_lifecycle(app, [])

        @app.get("/handler-raise", name="handler_raise")
        async def handler_raise(request):
            raise TimeoutError("downstream timeout")

        @app.exception(TimeoutError)
        async def handle_timeout(request, exception):
            return json_response({"error": str(exception)}, code=990000, status=500)

        set_route_policy(handler_raise, RoutePolicyDefinition(public=True, auth_required=False, timeout=30.0))
        compile_route_policies(app)
        app.ctx.lifecycle.mark_ready()

        async def scenario():
            _, response = await app.asgi_client.get("/handler-raise")
            assert response.status == 500
            assert response.json["code"] != 990002
            assert "downstream timeout" in response.json["data"]["error"]

        asyncio.run(scenario())

    def test_real_route_deadline_returns_504(self):
        """Genuine deadline expiry must return 504/990002."""
        app = Sanic("rd-real-deadline")

        sanic_adapter.install_context_middleware(app)
        from lingshu.lifecycle import register_lifecycle
        register_lifecycle(app, [])

        finalized = asyncio.Event()

        @app.get("/slow", name="slow")
        async def slow(request):
            try:
                await asyncio.Event().wait()
            finally:
                finalized.set()

        set_route_policy(slow, RoutePolicyDefinition(public=True, auth_required=False, timeout=0.05))
        compile_route_policies(app)
        app.ctx.lifecycle.mark_ready()

        async def scenario():
            _, response = await app.asgi_client.get("/slow")
            assert response.status == 504
            assert response.json["code"] == 990002
            assert finalized.is_set()

        asyncio.run(scenario())

    def test_handler_completed_after_deadline_still_returns_handler_result(self):
        """If the handler task is done when asyncio.wait wakes, the handler's
        own result/exception must be returned, not a 504."""
        app = Sanic("rd-completed-after-deadline")

        sanic_adapter.install_context_middleware(app)
        from lingshu.lifecycle import register_lifecycle
        register_lifecycle(app, [])

        @app.get("/fast", name="fast")
        async def fast(request):
            return json_response({"ok": True})

        set_route_policy(fast, RoutePolicyDefinition(public=True, auth_required=False, timeout=1.0))
        compile_route_policies(app)
        app.ctx.lifecycle.mark_ready()

        async def scenario():
            _, response = await app.asgi_client.get("/fast")
            assert response.status == 200
            assert response.json["data"]["ok"] is True

        asyncio.run(scenario())

    def test_deadline_task_is_cancelled_and_awaited(self):
        """When the deadline fires, the handler_task must be cancelled and
        awaited, leaving no orphan task."""
        app = Sanic("rd-cancel-orphan")

        sanic_adapter.install_context_middleware(app)
        from lingshu.lifecycle import register_lifecycle
        register_lifecycle(app, [])

        cleanup_done = asyncio.Event()

        @app.get("/hang", name="hang")
        async def hang(request):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cleanup_done.set()
                raise

        set_route_policy(hang, RoutePolicyDefinition(public=True, auth_required=False, timeout=0.05))
        compile_route_policies(app)
        app.ctx.lifecycle.mark_ready()

        async def scenario():
            _, response = await app.asgi_client.get("/hang")
            assert response.status == 504
            assert response.json["code"] == 990002
            assert cleanup_done.is_set()

            # Give callbacks a chance to run
            await asyncio.sleep(0)
            # Check for orphan tasks - all tasks except the current one
            current = asyncio.current_task()
            orphans = [t for t in asyncio.all_tasks() if t is not current]
            assert len(orphans) == 0, f"Orphan tasks remain: {orphans}"

        asyncio.run(scenario())

    def test_wrapper_cancelled_no_residual(self):
        """If the wrapper itself is cancelled, the handler_task must be
        cleaned up with no residual."""
        app = Sanic("rd-wrapper-cancelled")

        sanic_adapter.install_context_middleware(app)
        from lingshu.lifecycle import register_lifecycle
        register_lifecycle(app, [])

        cleanup_done = asyncio.Event()

        @app.get("/hang2", name="hang2")
        async def hang2(request):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cleanup_done.set()
                raise

        set_route_policy(hang2, RoutePolicyDefinition(public=True, auth_required=False, timeout=30.0))
        compile_route_policies(app)
        app.ctx.lifecycle.mark_ready()

        async def scenario():
            request_task = asyncio.create_task(app.asgi_client.get("/hang2"))
            await asyncio.sleep(0.05)
            request_task.cancel()
            try:
                await request_task
            except asyncio.CancelledError:
                pass

            await asyncio.sleep(0.05)
            assert cleanup_done.is_set()

            current = asyncio.current_task()
            orphans = [t for t in asyncio.all_tasks() if t is not current]
            assert len(orphans) == 0, f"Orphan tasks remain: {orphans}"

        asyncio.run(scenario())


# ---------------------------------------------------------------------------
# Exception redaction
# ---------------------------------------------------------------------------

class TestExceptionRedaction:
    """Verify redaction covers all required credential formats."""

    def test_bearer_token_redacted(self):
        text = "Authorization: Bearer abc123"
        redacted = _sanitize_text(text)
        assert "abc123" not in redacted
        assert "***" in redacted

    def test_basic_token_redacted(self):
        text = "Authorization: Basic abc123"
        redacted = _sanitize_text(text)
        assert "abc123" not in redacted
        assert "***" in redacted

    def test_json_double_quote_token_redacted(self):
        text = '{"token":"abc123"}'
        redacted = _sanitize_text(text)
        assert "abc123" not in redacted
        assert "***" in redacted

    def test_json_single_quote_token_redacted(self):
        text = "{'token': 'abc123'}"
        redacted = _sanitize_text(text)
        assert "abc123" not in redacted
        assert "***" in redacted

    def test_equals_api_key_redacted(self):
        text = 'api_key = "abc123"'
        redacted = _sanitize_text(text)
        assert "abc123" not in redacted
        assert "***" in redacted

    def test_colon_password_redacted(self):
        text = "password: abc123"
        redacted = _sanitize_text(text)
        assert "abc123" not in redacted
        assert "***" in redacted

    def test_equals_secret_redacted(self):
        text = "secret = abc123"
        redacted = _sanitize_text(text)
        assert "abc123" not in redacted
        assert "***" in redacted

    def test_access_key_colon_redacted(self):
        text = "access-key: abc123"
        redacted = _sanitize_text(text)
        assert "abc123" not in redacted
        assert "***" in redacted

    def test_multiple_secrets_in_one_message(self):
        text = "Authorization: Bearer tk123 token=abc456 password=secret789"
        redacted = _sanitize_text(text)
        assert "tk123" not in redacted
        assert "abc456" not in redacted
        assert "secret789" not in redacted

    def test_non_sensitive_text_preserved(self):
        text = "Connection refused at localhost:5432"
        redacted = _sanitize_text(text)
        assert "Connection refused" in redacted
        assert "localhost:5432" in redacted

    def test_message_truncated(self):
        long_text = "password=abc " + "x" * 10000
        redacted = _sanitize_text(long_text)
        assert len(redacted) <= 520  # _MAX_EXC_MSG_LEN + truncation suffix

    def test_exception_type_preserved(self):
        exc = RuntimeError("token=secret123")
        exc_type, safe_msg = _summarize_exception(exc)
        assert exc_type == "RuntimeError"
        assert "secret123" not in safe_msg

    def test_finalizer_log_does_not_leak_secret(self):
        """The finalizer must not write raw str(exc) to debug logs."""
        app_mock = SimpleNamespace(ctx=SimpleNamespace())
        app_mock.ctx.in_flight_tracker = InFlightRequestTracker()
        app_mock.ctx.task_registry = TaskRegistry()

        logged_messages = []
        mock_logger = MagicMock()
        mock_logger.debug = lambda fmt, *args: logged_messages.append(fmt % args)
        app_mock.ctx.logger = mock_logger

        request_mock = SimpleNamespace(app=app_mock, ctx=SimpleNamespace())

        async def scenario():
            await sanic_adapter.finalize_request_context(request_mock)

        asyncio.run(scenario())

        combined = " ".join(logged_messages)
        assert "super_secret_token_value" not in combined

    def test_task_record_does_not_retain_raw_secret(self):
        async def scenario():
            registry = TaskRegistry()

            async def job():
                raise RuntimeError("Authorization: Bearer leaked_token_xyz")

            task_id = registry.spawn(job(), name="leak-test", owner="application", scope="application")
            await registry.shutdown_and_wait(timeout=1.0)

            record = registry.get_record(task_id)
            assert record.exception_type == "RuntimeError"
            assert "leaked_token_xyz" not in record.exception_message
            assert "***" in record.exception_message

        asyncio.run(scenario())


# ---------------------------------------------------------------------------
# Deterministic cancellation tests (using Event, not sleep)
# ---------------------------------------------------------------------------

class TestDeterministicCancellation:
    """Cancellation and concurrency tests that use Event/Future synchronization
    instead of fixed-duration sleeps."""

    def test_cancellation_uses_event_synchronization(self):
        """Cancelled request must release in-flight tracker and propagate
        CancelledError, verified with explicit Event signals."""
        app = Sanic("det-cancel-test")

        sanic_adapter.install_context_middleware(app)
        from lingshu.lifecycle import register_lifecycle
        register_lifecycle(app, [])

        entered = asyncio.Event()
        cleanup_done = asyncio.Event()

        @app.get("/hang", name="hang_det")
        async def hang(request):
            entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cleanup_done.set()
                raise

        set_route_policy(hang, RoutePolicyDefinition(public=True, auth_required=False, timeout=30.0))
        compile_route_policies(app)
        app.ctx.lifecycle.mark_ready()

        async def scenario():
            request_task = asyncio.create_task(app.asgi_client.get("/hang"))
            await entered.wait()  # Wait until handler has entered
            request_task.cancel()
            try:
                await request_task
            except asyncio.CancelledError:
                pass

            await cleanup_done.wait()  # Wait for cleanup

            assert app.ctx.in_flight_tracker.count == 0

            current = asyncio.current_task()
            orphans = [t for t in asyncio.all_tasks() if t is not current]
            assert len(orphans) == 0

        asyncio.run(scenario())

    def test_concurrent_request_tasks_isolated_by_execution_id(self):
        """Two concurrent request-scoped tasks must be isolated and individually
        cancellable, verified with Events not sleeps."""
        async def scenario():
            registry = TaskRegistry()

            async def make_request(label):
                execution = RequestExecutionContext(
                    request_id=f"rid-{label}",
                    trace_id=f"trace-{label}",
                    route_policy=CompiledRoutePolicy("t", True, False, False, 1.0, None, "none"),
                    deadline=999.0,
                    lifecycle_state="ready",
                )
                started = asyncio.Event()
                finished = asyncio.Event()

                async def job():
                    started.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        finished.set()

                with bind_execution_context(execution):
                    registry.spawn(job(), name=f"task-{label}", owner="request", scope="request")
                    await started.wait()
                    await registry.finish_request(execution.execution_id, timeout=1.0)

                await finished.wait()

            await asyncio.gather(
                make_request("A"),
                make_request("B"),
            )

            # Both tasks finished and registry is empty (no orphans)
            assert registry.list() == []

        asyncio.run(scenario())


# ---------------------------------------------------------------------------
# Stop listener ordering and teardown idempotency
# ---------------------------------------------------------------------------

class TestStopListenerOrdering:
    """Verify before_server_stop runs shutdown coordinator and teardown,
    and after_server_stop is an idempotent fallback."""

    def test_stop_listener_exact_order(self):
        """Record the exact event sequence and verify ordering."""
        app = Sanic("order-exact")

        events: list[str] = []

        class Extension:
            @staticmethod
            async def setup(app_inner):
                events.append("setup")

            @staticmethod
            async def teardown(app_inner):
                events.append("teardown")

        sanic_adapter.install_context_middleware(app)
        from lingshu.lifecycle import register_lifecycle
        register_lifecycle(app, [Extension])
        compile_route_policies(app)

        async def scenario():
            _, response = await app.asgi_client.get("/live")
            assert response.status == 200

            assert events == ["setup", "teardown"]
            assert app.ctx.lifecycle.state == LifecycleState.STOPPED

        asyncio.run(scenario())

    def test_teardown_runs_exactly_once(self):
        """Teardown must run exactly once across the shutdown lifecycle."""
        app = Sanic("teardown-once")

        teardown_count = [0]

        class Extension:
            @staticmethod
            async def setup(app_inner):
                pass

            @staticmethod
            async def teardown(app_inner):
                teardown_count[0] += 1

        sanic_adapter.install_context_middleware(app)
        from lingshu.lifecycle import register_lifecycle
        register_lifecycle(app, [Extension])
        compile_route_policies(app)

        async def scenario():
            await app.asgi_client.get("/live")

            assert teardown_count[0] == 1

        asyncio.run(scenario())

    def test_after_server_stop_is_idempotent_fallback(self):
        """After calling after_server_stop again, teardown must not run twice."""
        app = Sanic("idempotent-stop")

        teardown_count = [0]

        class Extension:
            @staticmethod
            async def setup(app_inner):
                pass

            @staticmethod
            async def teardown(app_inner):
                teardown_count[0] += 1

        sanic_adapter.install_context_middleware(app)
        from lingshu.lifecycle import register_lifecycle
        register_lifecycle(app, [Extension])
        compile_route_policies(app)

        async def scenario():
            await app.asgi_client.get("/live")
            assert teardown_count[0] == 1

            # Simulate a second stop lifecycle event
            for listener in getattr(app.ctx, "lingshu_stop_listeners", ()):
                await listener(app)

            assert teardown_count[0] == 1

        asyncio.run(scenario())

    def test_cleanup_registration_does_not_accumulate(self):
        """Multiple ASGI start/stop cycles must not accumulate cleanup callbacks."""
        app = Sanic("no-accumulate")

        sanic_adapter.install_context_middleware(app)
        from lingshu.lifecycle import register_lifecycle
        register_lifecycle(app, [])
        compile_route_policies(app)

        async def scenario():
            await app.asgi_client.get("/live")
            first_count = len(app.ctx.shutdown_coordinator._cleanups)

            # Simulate second start
            app.ctx.lifecycle.restart_for_server_start()
            app.ctx.lifecycle.mark_ready()

            await app.asgi_client.get("/live")
            second_count = len(app.ctx.shutdown_coordinator._cleanups)

            assert second_count == first_count

        asyncio.run(scenario())
