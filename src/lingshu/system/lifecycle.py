from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum

from lingshu.response import json_response


class LifecycleState(str, Enum):
    STARTING = "starting"
    READY = "ready"
    DRAINING = "draining"
    STOPPING = "stopping"
    STOPPED = "stopped"


class LifecycleError(RuntimeError):
    pass


_TRANSITIONS = {
    LifecycleState.STARTING: {LifecycleState.READY, LifecycleState.DRAINING, LifecycleState.STOPPING},
    LifecycleState.READY: {LifecycleState.DRAINING, LifecycleState.STOPPING},
    LifecycleState.DRAINING: {LifecycleState.STOPPING},
    LifecycleState.STOPPING: {LifecycleState.STOPPED},
    LifecycleState.STOPPED: set(),
}


class ApplicationLifecycle:
    def __init__(self):
        self.state = LifecycleState.STARTING

    @property
    def live(self) -> bool:
        return self.state is not LifecycleState.STOPPED

    @property
    def ready(self) -> bool:
        return self.state is LifecycleState.READY

    def transition(self, next_state: LifecycleState):
        if next_state not in _TRANSITIONS[self.state]:
            raise LifecycleError(f"Illegal lifecycle transition: {self.state.value} -> {next_state.value}")
        self.state = next_state

    def restart_for_server_start(self):
        if self.state is LifecycleState.STOPPED:
            self.state = LifecycleState.STARTING

    def mark_ready(self):
        self.transition(LifecycleState.READY)

    def start_draining(self):
        if self.state is LifecycleState.DRAINING:
            return
        if self.state is LifecycleState.STOPPING:
            return
        if self.state is LifecycleState.STOPPED:
            return
        self.transition(LifecycleState.DRAINING)

    def start_stopping(self):
        if self.state is LifecycleState.STOPPED:
            return
        if self.state is LifecycleState.STARTING:
            self.transition(LifecycleState.STOPPING)
        elif self.state is LifecycleState.READY:
            self.transition(LifecycleState.DRAINING)
            self.transition(LifecycleState.STOPPING)
        elif self.state is LifecycleState.DRAINING:
            self.transition(LifecycleState.STOPPING)
        elif self.state is not LifecycleState.STOPPING:
            raise LifecycleError(f"Cannot stop from {self.state.value}")

    def mark_stopped(self):
        if self.state is LifecycleState.STOPPED:
            return
        self.transition(LifecycleState.STOPPED)

    def ensure_accepting_work(self):
        if not self.ready:
            raise LifecycleError("Application is not accepting business work")


def lifecycle_payload(lifecycle: ApplicationLifecycle):
    return {
        "state": lifecycle.state.value,
        "live": lifecycle.live,
        "ready": lifecycle.ready,
    }


class InFlightRequestTracker:
    def __init__(self):
        self._count = 0
        self._idle = asyncio.Event()
        self._idle.set()

    @property
    def count(self) -> int:
        return self._count

    @asynccontextmanager
    async def track(self):
        self.enter()
        try:
            yield
        finally:
            self.exit()

    def enter(self):
        if self._count == 0:
            self._idle.clear()
        self._count += 1

    def exit(self):
        if self._count <= 0:
            raise LifecycleError("In-flight request count cannot become negative")
        self._count -= 1
        if self._count == 0:
            self._idle.set()

    async def wait_until_idle(self, timeout: float):
        if self._count == 0:
            return True
        await asyncio.wait_for(self._idle.wait(), timeout=max(0.0, timeout))
        return True


def install_health_routes(app, lifecycle: ApplicationLifecycle):
    health_paths = {"/live", "/ready", "/health"}

    @app.middleware("request")
    async def reject_business_while_not_ready(request):
        if request.path in health_paths:
            return None
        if not lifecycle.ready:
            return json_response(
                {"state": lifecycle.state.value},
                code=503,
                msg="Application is not accepting business work",
                status=503,
            )

    @app.exception(LifecycleError)
    async def lifecycle_error(request, exception):
        return json_response({"state": lifecycle.state.value}, code=503, msg=str(exception), status=503)

    existing_paths = {f"/{str(route.path).lstrip('/')}" for route in app.router.routes_all.values()}

    if "/live" not in existing_paths:
        @app.get("/live", name="lingshu.live")
        async def live(request):
            status = 200 if lifecycle.live else 503
            return json_response(lifecycle_payload(lifecycle), status=status)
        _mark_health_policy(live)

    if "/ready" not in existing_paths:
        @app.get("/ready", name="lingshu.ready")
        async def ready(request):
            status = 200 if lifecycle.ready else 503
            return json_response(lifecycle_payload(lifecycle), status=status)
        _mark_health_policy(ready)

    if "/health" not in existing_paths:
        @app.get("/health", name="lingshu.health")
        async def health(request):
            status = 200 if lifecycle.live else 503
            return json_response(lifecycle_payload(lifecycle), status=status)
        _mark_health_policy(health)


def _mark_health_policy(handler):
    from lingshu.system.policy import RoutePolicyDefinition, set_route_policy

    set_route_policy(
        handler,
        RoutePolicyDefinition(
            public=True,
            auth_required=False,
            maintenance_check=False,
            timeout=1.0,
            audit_level="none",
        ),
    )


@dataclass
class ShutdownResult:
    state: LifecycleState
    errors: list[BaseException] = field(default_factory=list)
    timed_out: bool = False
    unfinished_tasks: int = 0
    unfinished_requests: int = 0
    already_stopped: bool = False


class ShutdownCoordinator:
    def __init__(
        self,
        lifecycle: ApplicationLifecycle,
        *,
        shutdown_timeout: float,
        cleanup_timeout: float,
        in_flight_tracker: InFlightRequestTracker | None = None,
        task_registry=None,
        monotonic=time.monotonic,
    ):
        self.lifecycle = lifecycle
        self.shutdown_timeout = shutdown_timeout
        self.cleanup_timeout = cleanup_timeout
        self.in_flight_tracker = in_flight_tracker
        self.task_registry = task_registry
        self.monotonic = monotonic
        self._cleanups = []
        self._result: ShutdownResult | None = None
        self._lock = asyncio.Lock()

    def add_cleanup(self, callback):
        self._cleanups.append(callback)

    async def shutdown(self) -> ShutdownResult:
        async with self._lock:
            if self._result is not None:
                self._result.already_stopped = True
                return self._result
            if self.lifecycle.state is LifecycleState.STOPPED:
                self._result = ShutdownResult(state=self.lifecycle.state, already_stopped=True)
                return self._result
            self._result = await self._run_shutdown()
            return self._result

    def _remaining(self, deadline: float) -> float:
        return max(0.0, deadline - self.monotonic())

    async def _run_shutdown(self) -> ShutdownResult:
        deadline = self.monotonic() + self.shutdown_timeout
        self.lifecycle.start_draining()
        errors: list[BaseException] = []
        timed_out = False
        unfinished_tasks = 0
        unfinished_requests = 0

        if self.in_flight_tracker is not None:
            try:
                await self.in_flight_tracker.wait_until_idle(self._remaining(deadline))
            except TimeoutError:
                timed_out = True
                unfinished_requests = self.in_flight_tracker.count

        self.lifecycle.start_stopping()

        if self.task_registry is not None:
            task_result = await self.task_registry.shutdown_and_wait(timeout=self._remaining(deadline))
            unfinished_tasks = len(task_result.unfinished)
            timed_out = timed_out or task_result.timed_out

        for callback in reversed(self._cleanups):
            remaining = self._remaining(deadline)
            if remaining <= 0:
                timed_out = True
                break
            try:
                await asyncio.wait_for(callback(), timeout=min(self.cleanup_timeout, remaining))
            except TimeoutError as exc:
                timed_out = True
                errors.append(exc)
                continue
            except Exception as exc:
                errors.append(exc)
        self.lifecycle.mark_stopped()
        return ShutdownResult(
            state=self.lifecycle.state,
            errors=errors,
            timed_out=timed_out,
            unfinished_tasks=unfinished_tasks,
            unfinished_requests=unfinished_requests,
        )
