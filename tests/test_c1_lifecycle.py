import asyncio

import pytest
from sanic import Sanic

from lingshu.response import json_response
from lingshu.system.lifecycle import (
    ApplicationLifecycle,
    LifecycleError,
    LifecycleState,
    ShutdownCoordinator,
    install_health_routes,
)


def test_lifecycle_state_transition_matrix():
    lifecycle = ApplicationLifecycle()

    assert lifecycle.state == LifecycleState.STARTING
    lifecycle.mark_ready()
    assert lifecycle.state == LifecycleState.READY
    lifecycle.start_draining()
    assert lifecycle.state == LifecycleState.DRAINING
    lifecycle.start_stopping()
    assert lifecycle.state == LifecycleState.STOPPING
    lifecycle.mark_stopped()
    assert lifecycle.state == LifecycleState.STOPPED

    with pytest.raises(LifecycleError):
        lifecycle.mark_ready()


def test_health_live_ready_and_drain_semantics():
    app = Sanic("health-runtime")
    lifecycle = ApplicationLifecycle()
    lifecycle.mark_ready()
    install_health_routes(app, lifecycle)

    async def scenario():
        _, live = await app.asgi_client.get("/live")
        _, ready = await app.asgi_client.get("/ready")
        _, health = await app.asgi_client.get("/health")
        assert live.status == 200
        assert ready.status == 200
        assert health.status == 200
        assert health.json["data"]["state"] == "ready"

        lifecycle.start_draining()
        _, ready_after_drain = await app.asgi_client.get("/ready")
        _, health_after_drain = await app.asgi_client.get("/health")
        assert ready_after_drain.status == 503
        assert health_after_drain.json["data"]["state"] == "draining"

    asyncio.run(scenario())


def test_drain_rejects_new_business_work_but_allows_health():
    app = Sanic("drain-business")
    lifecycle = ApplicationLifecycle()
    lifecycle.mark_ready()
    install_health_routes(app, lifecycle)

    @app.get("/business")
    async def business(request):
        return json_response({"ok": True})

    async def scenario():
        _, ok = await app.asgi_client.get("/business")
        assert ok.status == 200
        lifecycle.start_draining()
        _, rejected = await app.asgi_client.get("/business")
        assert rejected.status == 503
        _, live = await app.asgi_client.get("/live")
        assert live.status == 200

    asyncio.run(scenario())


def test_shutdown_coordinator_runs_cleanup_reverse_order_and_is_idempotent():
    async def scenario():
        lifecycle = ApplicationLifecycle()
        lifecycle.mark_ready()
        order = []

        async def first():
            order.append("first")

        async def second():
            order.append("second")

        coordinator = ShutdownCoordinator(lifecycle, shutdown_timeout=1.0, cleanup_timeout=1.0)
        coordinator.add_cleanup(first)
        coordinator.add_cleanup(second)

        result1 = await coordinator.shutdown()
        result2 = await coordinator.shutdown()

        assert order == ["second", "first"]
        assert result1.state == LifecycleState.STOPPED
        assert result2.already_stopped is True

    asyncio.run(scenario())


def test_shutdown_coordinator_collects_cleanup_failures_and_continues():
    async def scenario():
        lifecycle = ApplicationLifecycle()
        lifecycle.mark_ready()
        order = []

        async def bad():
            order.append("bad")
            raise RuntimeError("cleanup failed")

        async def good():
            order.append("good")

        coordinator = ShutdownCoordinator(lifecycle, shutdown_timeout=1.0, cleanup_timeout=1.0)
        coordinator.add_cleanup(good)
        coordinator.add_cleanup(bad)

        result = await coordinator.shutdown()

        assert order == ["bad", "good"]
        assert len(result.errors) == 1
        assert "cleanup failed" in str(result.errors[0])
        assert lifecycle.state == LifecycleState.STOPPED

    asyncio.run(scenario())
