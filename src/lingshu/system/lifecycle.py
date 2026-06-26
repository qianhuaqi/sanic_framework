from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum

from lingshu.response import json_response


class LifecycleState(StrEnum):
    STARTING = "starting"
    READY = "ready"
    DRAINING = "draining"
    STOPPING = "stopping"
    STOPPED = "stopped"


class LifecycleError(RuntimeError):
    pass


_TRANSITIONS = {
    LifecycleState.STARTING: {LifecycleState.READY, LifecycleState.STOPPING},
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

    def mark_ready(self):
        self.transition(LifecycleState.READY)

    def start_draining(self):
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

    if "/ready" not in existing_paths:
        @app.get("/ready", name="lingshu.ready")
        async def ready(request):
            status = 200 if lifecycle.ready else 503
            return json_response(lifecycle_payload(lifecycle), status=status)

    if "/health" not in existing_paths:
        @app.get("/health", name="lingshu.health")
        async def health(request):
            status = 200 if lifecycle.live else 503
            return json_response(lifecycle_payload(lifecycle), status=status)


@dataclass
class ShutdownResult:
    state: LifecycleState
    errors: list[BaseException] = field(default_factory=list)
    already_stopped: bool = False


class ShutdownCoordinator:
    def __init__(self, lifecycle: ApplicationLifecycle, *, shutdown_timeout: float, cleanup_timeout: float):
        self.lifecycle = lifecycle
        self.shutdown_timeout = shutdown_timeout
        self.cleanup_timeout = cleanup_timeout
        self._cleanups = []
        self._shutdown_started = False

    def add_cleanup(self, callback):
        self._cleanups.append(callback)

    async def shutdown(self) -> ShutdownResult:
        if self.lifecycle.state is LifecycleState.STOPPED:
            return ShutdownResult(state=self.lifecycle.state, already_stopped=True)
        if self._shutdown_started:
            return ShutdownResult(state=self.lifecycle.state, already_stopped=self.lifecycle.state is LifecycleState.STOPPED)
        self._shutdown_started = True
        self.lifecycle.start_stopping()
        errors: list[BaseException] = []
        for callback in reversed(self._cleanups):
            try:
                await asyncio.wait_for(callback(), timeout=self.cleanup_timeout)
            except Exception as exc:
                errors.append(exc)
        self.lifecycle.mark_stopped()
        return ShutdownResult(state=self.lifecycle.state, errors=errors)
