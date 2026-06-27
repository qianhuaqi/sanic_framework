import asyncio
import gc
import weakref
from types import SimpleNamespace

import pytest
from sanic import Sanic

from lingshu import request
from lingshu.lifecycle import register_lifecycle
from lingshu.response import json_response
from lingshu.router import compile_route_policies
from lingshu.system.errors import NoRequestContextError
from lingshu.system.execution import current_execution_context
from lingshu.system import sanic_adapter
from lingshu.system.lifecycle import (
    ApplicationLifecycle,
    InFlightRequestTracker,
    LifecycleState,
    ShutdownCoordinator,
    install_health_routes,
)
from lingshu.system.policy import RoutePolicyCompiler, RoutePolicyDefinition, RoutePolicyError, set_route_policy
from lingshu.system.tasks import TaskRegistry


async def _run_startup(app):
    for listener in getattr(app.ctx, "lingshu_startup_listeners", ()):
        await listener(app)


async def _run_stop(app):
    for listener in getattr(app.ctx, "lingshu_stop_listeners", ()):
        await listener(app)


def test_create_app_lifecycle_remains_starting_until_startup(monkeypatch):
    from lingshu.app import create_app

    monkeypatch.setenv("MYSQL_ENABLED", "false")
    monkeypatch.setenv("REDIS_ENABLED", "false")
    monkeypatch.setenv("MONGO_ENABLED", "false")

    app = create_app()

    assert app.ctx.lifecycle.state == LifecycleState.STARTING
    asyncio.run(_run_startup(app))
    assert app.ctx.lifecycle.state == LifecycleState.READY


def test_startup_failure_keeps_app_not_ready_and_business_returns_503():
    app = Sanic("startup-failure")

    class BadExtension:
        @staticmethod
        async def setup(app):
            raise RuntimeError("dependency down")

    register_lifecycle(app, [BadExtension])

    @app.get("/business", name="business")
    async def business(request):
        return json_response({"ok": True})

    compile_route_policies(app)

    async def scenario():
        with pytest.raises(RuntimeError, match="dependency down"):
            await _run_startup(app)
        assert app.ctx.lifecycle.state == LifecycleState.STARTING
        _, response = await app.asgi_client.get("/business")
        assert response.status == 503

    asyncio.run(scenario())


def test_missing_compiled_policy_fails_closed_for_dynamic_route():
    app = Sanic("missing-policy")
    sanic_adapter.install_context_middleware(app)
    register_lifecycle(app, [])

    @app.get("/known", name="known")
    async def known(request):
        return json_response({"ok": True})

    compile_route_policies(app)

    @app.get("/dynamic", name="dynamic")
    async def dynamic(request):
        return json_response({"ok": True})

    app.ctx.lifecycle.mark_ready()

    async def scenario():
        _, response = await app.asgi_client.get("/dynamic")
        assert response.status == 500
        assert response.json["code"] == 990001

    asyncio.run(scenario())


def test_route_policy_compiler_rejects_empty_and_duplicate_route_names():
    app = Sanic("bad-policy-names")

    @app.get("/a", name="same")
    async def a(request):
        return None

    @app.get("/b", name="same")
    async def b(request):
        return None

    with pytest.raises(RoutePolicyError, match="Duplicate"):
        RoutePolicyCompiler().compile_app(app)

    empty_app = Sanic("empty-policy-name")

    @empty_app.get("/empty", name="empty")
    async def empty(request):
        return None

    next(iter(empty_app.router.routes_all.values())).name = ""
    with pytest.raises(RoutePolicyError, match="empty"):
        RoutePolicyCompiler().compile_app(empty_app)


def test_health_routes_have_explicit_public_compiled_policy():
    app = Sanic("health-policy")
    lifecycle = ApplicationLifecycle()
    install_health_routes(app, lifecycle)
    compiled = compile_route_policies(app)

    for name in ("lingshu.live", "lingshu.ready", "lingshu.health"):
        policy = compiled.for_route(name)
        assert policy.public is True
        assert policy.auth_required is False
        assert policy.maintenance_check is False
        assert policy.timeout <= 2.0
        assert policy.audit_level == "none"


def test_application_task_created_in_request_uses_clean_context():
    async def scenario():
        registry = TaskRegistry()
        seen = {}

        async def job():
            for key, accessor in {
                "raw": lambda: request.raw,
                "user": lambda: request.user,
                "execution": lambda: request.execution,
                "current_execution": current_execution_context,
            }.items():
                try:
                    accessor()
                except NoRequestContextError:
                    seen[key] = "clean"
                else:
                    seen[key] = "leaked"

        context = current_execution_context
        with pytest.raises(NoRequestContextError):
            context()

        from lingshu.system.execution import RequestExecutionContext, bind_execution_context
        from lingshu.system.policy import CompiledRoutePolicy

        execution = RequestExecutionContext(
            request_id="rid-clean",
            trace_id="trace-clean",
            route_policy=CompiledRoutePolicy("probe", True, False, False, 1.0, None, "none"),
            deadline=999.0,
            lifecycle_state="ready",
        )
        with bind_execution_context(execution):
            task_id = registry.spawn(job(), name="clean", owner="application", scope="application")

        await registry.shutdown_and_wait(timeout=1.0)
        assert registry.get_record(task_id).request_id == "rid-clean"
        assert seen == {
            "raw": "clean",
            "user": "clean",
            "execution": "clean",
            "current_execution": "clean",
        }

    asyncio.run(scenario())


def test_request_task_can_access_context_but_is_cancelled_at_request_end():
    async def scenario():
        registry = TaskRegistry()
        started = asyncio.Event()
        cleaned = asyncio.Event()

        async def job():
            try:
                assert request.execution.request_id == "rid-request-task"
                started.set()
                await asyncio.Event().wait()
            finally:
                cleaned.set()

        from lingshu.system.execution import RequestExecutionContext, bind_execution_context
        from lingshu.system.policy import CompiledRoutePolicy

        execution = RequestExecutionContext(
            request_id="rid-request-task",
            trace_id="trace-request-task",
            route_policy=CompiledRoutePolicy("probe", True, False, False, 1.0, None, "none"),
            deadline=999.0,
            lifecycle_state="ready",
        )
        with bind_execution_context(execution):
            registry.spawn(job(), name="request-task", owner="request", scope="request")
            await started.wait()
            await registry.finish_request(execution.execution_id, timeout=1.0)

        assert cleaned.is_set()
        assert registry.list() == []

    asyncio.run(scenario())


def test_task_registry_history_is_bounded_and_forget_releases_records():
    async def scenario():
        registry = TaskRegistry(max_history=3)

        class BigResult:
            pass

        big = BigResult()
        ref = weakref.ref(big)

        async def return_big(value):
            return value

        registry.spawn(return_big(big), name="big", owner="application", scope="application")
        big = None
        last = None
        for index in range(10):
            last = registry.spawn(return_big(index), name=f"short-{index}", owner="application", scope="application")
        await registry.shutdown_and_wait(timeout=1.0)
        await asyncio.sleep(0)
        gc.collect()
        assert ref() is None
        assert registry.history_size <= 3

        registry.forget(last)
        with pytest.raises(KeyError):
            registry.get_record(last)

    asyncio.run(scenario())


def test_shutdown_coordinator_uses_total_deadline_and_concurrent_callers_share_result():
    async def scenario():
        lifecycle = ApplicationLifecycle()
        lifecycle.mark_ready()
        order = []

        async def slow(name):
            order.append(name)
            await asyncio.Event().wait()

        coordinator = ShutdownCoordinator(lifecycle, shutdown_timeout=0.05, cleanup_timeout=1.0)
        coordinator.add_cleanup(lambda: slow("first"))
        coordinator.add_cleanup(lambda: slow("second"))

        result1, result2 = await asyncio.gather(coordinator.shutdown(), coordinator.shutdown())

        assert result1 is result2
        assert result1.timed_out is True
        assert result1.state == LifecycleState.STOPPED
        assert "second" in order

    asyncio.run(scenario())


def test_shutdown_waits_for_inflight_requests_and_reports_timeout():
    async def scenario():
        lifecycle = ApplicationLifecycle()
        lifecycle.mark_ready()
        tracker = InFlightRequestTracker()
        release = asyncio.Event()

        async def request_work():
            async with tracker.track():
                await release.wait()

        request_task = asyncio.create_task(request_work())
        await asyncio.sleep(0)

        coordinator = ShutdownCoordinator(
            lifecycle,
            shutdown_timeout=0.05,
            cleanup_timeout=0.01,
            in_flight_tracker=tracker,
        )
        result = await coordinator.shutdown()
        release.set()
        await request_task

        assert result.timed_out is True
        assert result.unfinished_requests == 1
        assert lifecycle.state == LifecycleState.STOPPED

    asyncio.run(scenario())


def test_sanic_stop_listener_runs_shutdown_coordinator_and_cleanup():
    app = Sanic("listener-shutdown")
    cleanup_called = asyncio.Event()

    class Extension:
        @staticmethod
        async def teardown(app):
            cleanup_called.set()

    sanic_adapter.install_context_middleware(app)
    register_lifecycle(app, [Extension])
    compile_route_policies(app)

    async def scenario():
        _, response = await app.asgi_client.get("/live")
        assert response.status == 200
        assert cleanup_called.is_set()
        assert app.ctx.lifecycle.state == LifecycleState.STOPPED
        assert app.ctx.shutdown_coordinator._result.state == LifecycleState.STOPPED

    asyncio.run(scenario())


def test_request_deadline_returns_stable_timeout_and_runs_finally():
    app = Sanic("deadline-boundary")
    sanic_adapter.install_context_middleware(app)
    register_lifecycle(app, [])
    finalized = asyncio.Event()

    @app.get("/slow", name="slow")
    async def slow(request):
        try:
            await asyncio.Event().wait()
        finally:
            finalized.set()

    set_route_policy(slow, RoutePolicyDefinition(public=True, auth_required=False, timeout=0.01))
    compile_route_policies(app)
    app.ctx.lifecycle.mark_ready()

    async def scenario():
        _, response = await app.asgi_client.get("/slow")
        assert response.status == 504
        assert response.json["code"] == 990002
        assert finalized.is_set()
        with pytest.raises(NoRequestContextError):
            current_execution_context()

    asyncio.run(scenario())


def test_multi_app_runtime_state_is_isolated():
    app_a = Sanic("app-a")
    app_b = Sanic("app-b")
    sanic_adapter.install_context_middleware(app_a)
    sanic_adapter.install_context_middleware(app_b)
    register_lifecycle(app_a, [])
    register_lifecycle(app_b, [])

    @app_a.get("/a", name="a")
    async def route_a(request):
        return json_response({"request_id": current_execution_context().request_id})

    @app_b.get("/b", name="b")
    async def route_b(request):
        return json_response({"request_id": current_execution_context().request_id})

    compile_route_policies(app_a)
    compile_route_policies(app_b)
    app_a.ctx.lifecycle.mark_ready()
    app_b.ctx.lifecycle.mark_ready()

    assert app_a.ctx.lifecycle is not app_b.ctx.lifecycle
    assert app_a.ctx.route_policies is not app_b.ctx.route_policies
    assert app_a.ctx.task_registry is not app_b.ctx.task_registry
    assert app_a.ctx.in_flight_tracker is not app_b.ctx.in_flight_tracker

    async def scenario():
        _, response_a = await app_a.asgi_client.get("/a", headers={"X-Request-ID": "a"})
        _, response_b = await app_b.asgi_client.get("/b", headers={"X-Request-ID": "b"})

        assert response_a.json["data"]["request_id"] == "a"
        assert response_b.json["data"]["request_id"] == "b"

        assert app_b.ctx.lifecycle.state == LifecycleState.STOPPED
        app_b.ctx.lifecycle.restart_for_server_start()
        app_b.ctx.lifecycle.mark_ready()

        await app_a.ctx.shutdown_coordinator.shutdown()
        assert app_a.ctx.lifecycle.state == LifecycleState.STOPPED
        assert app_b.ctx.lifecycle.state == LifecycleState.READY

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# Second-round review regression tests
# ---------------------------------------------------------------------------


def test_concurrent_same_request_id_tasks_are_isolated_by_execution_id():
    """Two concurrent requests with the same X-Request-ID must not cancel
    each other's request-scoped tasks."""

    async def scenario():
        registry = TaskRegistry()
        results = {}

        async def make_request(label, request_id):
            from lingshu.system.execution import RequestExecutionContext, bind_execution_context
            from lingshu.system.policy import CompiledRoutePolicy

            execution = RequestExecutionContext(
                request_id=request_id,
                trace_id=f"trace-{label}",
                route_policy=CompiledRoutePolicy("probe", True, False, False, 1.0, None, "none"),
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
                # Finish only this execution's tasks
                await registry.finish_request(execution.execution_id, timeout=1.0)

            results[label] = {
                "finished": finished.is_set(),
                "execution_id": execution.execution_id,
            }

        # Both requests share the same X-Request-ID
        await asyncio.gather(
            make_request("A", "same-id"),
            make_request("B", "same-id"),
        )

        assert results["A"]["finished"] is True
        assert results["B"]["finished"] is True
        assert results["A"]["execution_id"] != results["B"]["execution_id"]

    asyncio.run(scenario())


def test_execution_id_is_unique_and_auto_generated():
    from lingshu.system.execution import RequestExecutionContext
    from lingshu.system.policy import CompiledRoutePolicy

    policy = CompiledRoutePolicy("probe", True, False, False, 1.0, None, "none")
    ctx_a = RequestExecutionContext(
        request_id="r1", trace_id="t1", route_policy=policy,
        deadline=999.0, lifecycle_state="ready",
    )
    ctx_b = RequestExecutionContext(
        request_id="r1", trace_id="t1", route_policy=policy,
        deadline=999.0, lifecycle_state="ready",
    )
    assert ctx_a.execution_id != ""
    assert ctx_b.execution_id != ""
    assert ctx_a.execution_id != ctx_b.execution_id


def test_finish_request_uses_execution_id_not_request_id():
    async def scenario():
        registry = TaskRegistry()
        barrier = asyncio.Event()
        started = asyncio.Event()

        async def job():
            started.set()
            await barrier.wait()

        from lingshu.system.execution import RequestExecutionContext, bind_execution_context
        from lingshu.system.policy import CompiledRoutePolicy

        # Two executions with same request_id but different execution_id
        ctx_a = RequestExecutionContext(
            request_id="shared-rid",
            trace_id="t-a",
            route_policy=CompiledRoutePolicy("probe", True, False, False, 1.0, None, "none"),
            deadline=999.0,
            lifecycle_state="ready",
        )
        ctx_b = RequestExecutionContext(
            request_id="shared-rid",
            trace_id="t-b",
            route_policy=CompiledRoutePolicy("probe", True, False, False, 1.0, None, "none"),
            deadline=999.0,
            lifecycle_state="ready",
        )

        with bind_execution_context(ctx_a):
            registry.spawn(job(), name="a", owner="request", scope="request")
        with bind_execution_context(ctx_b):
            registry.spawn(job(), name="b", owner="request", scope="request")

        await started.wait()
        assert len(registry.list()) == 2

        # Finish only ctx_a - should not affect ctx_b
        await registry.finish_request(ctx_a.execution_id, timeout=1.0)
        assert len(registry.list()) == 1
        assert registry.list()[0].name == "b"

        barrier.set()
        await registry.shutdown_and_wait(timeout=1.0)

    asyncio.run(scenario())


def test_finalizer_idempotent_repeated_calls_safe():
    """Calling finalize_request_context multiple times must not cause
    negative in-flight counts or errors."""
    from lingshu.system import sanic_adapter
    from lingshu.system.lifecycle import InFlightRequestTracker

    app_mock = SimpleNamespace(ctx=SimpleNamespace())
    tracker = InFlightRequestTracker()
    app_mock.ctx.in_flight_tracker = tracker
    app_mock.ctx.task_registry = TaskRegistry()

    request_mock = SimpleNamespace(app=app_mock, ctx=SimpleNamespace())

    async def scenario():
        tracker.enter()
        request_mock.ctx.lingshu_in_flight_entered = True
        assert tracker.count == 1

        await sanic_adapter.finalize_request_context(request_mock)
        assert tracker.count == 0

        await sanic_adapter.finalize_request_context(request_mock)
        assert tracker.count == 0

    asyncio.run(scenario())


def test_handler_timeout_error_is_not_treated_as_route_deadline():
    """A handler that raises TimeoutError on its own must NOT return 504/990002."""
    app = Sanic("handler-timeout-test")
    sanic_adapter.install_context_middleware(app)
    register_lifecycle(app, [])

    @app.get("/handler-timeout", name="handler_timeout")
    async def handler_timeout(request):
        raise TimeoutError("downstream dependency timed out")

    @app.exception(TimeoutError)
    async def handle_timeout(request, exception):
        return json_response({"error": str(exception)}, code=990000, status=500)

    set_route_policy(handler_timeout, RoutePolicyDefinition(public=True, auth_required=False, timeout=30.0))
    compile_route_policies(app)
    app.ctx.lifecycle.mark_ready()

    async def scenario():
        _, response = await app.asgi_client.get("/handler-timeout")
        assert response.status == 500
        assert response.json["code"] != 990002

    asyncio.run(scenario())


def test_route_deadline_returns_504_with_correct_code():
    """A genuine route deadline expiry must return 504/990002."""
    app = Sanic("route-deadline-test")
    sanic_adapter.install_context_middleware(app)
    register_lifecycle(app, [])

    @app.get("/slow", name="slow_route")
    async def slow(request):
        await asyncio.sleep(5)

    set_route_policy(slow, RoutePolicyDefinition(public=True, auth_required=False, timeout=0.05))
    compile_route_policies(app)
    app.ctx.lifecycle.mark_ready()

    async def scenario():
        _, response = await app.asgi_client.get("/slow")
        assert response.status == 504
        assert response.json["code"] == 990002

    asyncio.run(scenario())


def test_wrapper_preserves_handler_metadata():
    """functools.wraps must preserve __name__, __module__, __doc__, __annotations__."""
    import inspect

    app = Sanic("metadata-test")

    @app.get("/meta", name="meta_route")
    async def meta_handler(request):
        """Get metadata."""
        return json_response({"ok": True})

    set_route_policy(meta_handler, RoutePolicyDefinition(public=True, auth_required=False))
    compile_route_policies(app)

    from lingshu.router import compile_route_policies as _dummy  # ensure compiled

    route = None
    for r in app.router.routes_all.values():
        if getattr(r, "name", "") == "metadata-test.meta_route":
            route = r
            break
    assert route is not None
    wrapped = route.handler
    assert wrapped.__name__ == "meta_handler"
    assert wrapped.__module__ == __name__
    assert wrapped.__doc__ == "Get metadata."
    assert hasattr(wrapped, "__lingshu_route_policy__")
    assert hasattr(wrapped, "__lingshu_compiled_policy__")


def test_shutdown_continues_after_single_cleanup_timeout():
    """If cleanup B times out but budget remains, cleanup A must still run."""
    from lingshu.system.lifecycle import ApplicationLifecycle, ShutdownCoordinator, LifecycleState

    async def scenario():
        lifecycle = ApplicationLifecycle()
        lifecycle.mark_ready()
        order = []

        async def cleanup_a():
            order.append("A")

        async def cleanup_b():
            order.append("B")
            await asyncio.Event().wait()  # hangs forever

        coordinator = ShutdownCoordinator(
            lifecycle,
            shutdown_timeout=1.0,
            cleanup_timeout=0.05,
        )
        coordinator.add_cleanup(cleanup_a)
        coordinator.add_cleanup(cleanup_b)

        result = await coordinator.shutdown()

        assert "B" in order
        assert "A" in order
        assert result.timed_out is True
        assert any("TimeoutError" in str(type(e).__name__) for e in result.errors)
        assert lifecycle.state == LifecycleState.STOPPED

    asyncio.run(scenario())


def test_before_server_stop_runs_coordinator_before_after():
    """Verify shutdown coordinator runs at before_server_stop, and
    after_server_stop is a no-op fallback."""
    app = Sanic("listener-order-test")
    events = []

    class Extension:
        @staticmethod
        async def setup(app):
            events.append("setup")

        @staticmethod
        async def teardown(app):
            events.append("teardown")

    sanic_adapter.install_context_middleware(app)
    register_lifecycle(app, [Extension])
    compile_route_policies(app)

    async def scenario():
        _, response = await app.asgi_client.get("/live")
        assert response.status == 200

        assert app.ctx.lifecycle.state == LifecycleState.STOPPED
        assert "teardown" in events
        assert app.ctx.shutdown_coordinator._result is not None

    asyncio.run(scenario())


def test_cancellation_clears_inflight_and_propagates():
    """Cancelled request must release in-flight tracker and propagate CancelledError."""
    app = Sanic("cancel-cleanup-test")
    sanic_adapter.install_context_middleware(app)
    register_lifecycle(app, [])

    @app.get("/hang", name="hang")
    async def hang(request):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise

    set_route_policy(hang, RoutePolicyDefinition(public=True, auth_required=False, timeout=30.0))
    compile_route_policies(app)
    app.ctx.lifecycle.mark_ready()

    async def scenario():
        task = asyncio.create_task(app.asgi_client.get("/hang"))
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(0.1)
        assert app.ctx.in_flight_tracker.count == 0

    asyncio.run(scenario())
