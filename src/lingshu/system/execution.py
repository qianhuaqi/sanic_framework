from __future__ import annotations

import asyncio
import contextvars
import time
from dataclasses import dataclass, field
from enum import StrEnum

from lingshu.system.errors import NoRequestContextError


class CancellationReason(StrEnum):
    CLIENT_DISCONNECT = "client_disconnect"
    REQUEST_TIMEOUT = "request_timeout"
    PARENT_FAILURE = "parent_failure"
    APPLICATION_DRAINING = "application_draining"
    MANUAL = "manual"


current_execution: contextvars.ContextVar["RequestExecutionContext | None"] = contextvars.ContextVar(
    "lingshu_current_execution",
    default=None,
)


class _ExecutionBinding:
    def __init__(self, context: "RequestExecutionContext"):
        self.context = context
        self.token = None
        self.reset_done = False

    def __enter__(self):
        if self.token is None:
            self.token = current_execution.set(self.context)
        return self.context

    def __exit__(self, exc_type, exc, tb):
        self.reset()

    def reset(self):
        if self.token is not None and not self.reset_done:
            current_execution.reset(self.token)
            self.reset_done = True
            self.token = None

    def detach_after_task(self):
        self.reset_done = True
        self.token = None
        self.context = None


@dataclass
class RequestExecutionContext:
    request_id: str
    trace_id: str
    route_policy: object
    deadline: float
    lifecycle_state: str
    operation_id: str | None = None
    cancel_reason: CancellationReason | None = None
    monotonic: object = time.monotonic
    extensions: dict[str, object] = field(default_factory=dict)

    @classmethod
    def child(
        cls,
        *,
        request_id: str,
        trace_id: str,
        route_policy,
        timeout: float,
        lifecycle_state: str,
        monotonic=time.monotonic,
        operation_id: str | None = None,
    ) -> "RequestExecutionContext":
        now = monotonic()
        child_deadline = now + timeout
        parent = current_execution.get()
        if parent is not None:
            child_deadline = min(parent.deadline, child_deadline)
        return cls(
            request_id=request_id,
            trace_id=trace_id,
            route_policy=route_policy,
            deadline=child_deadline,
            lifecycle_state=lifecycle_state,
            operation_id=operation_id,
            monotonic=monotonic,
        )

    @property
    def remaining(self) -> float:
        return max(0.0, self.deadline - self.monotonic())

    def cancel(self, reason: CancellationReason | str):
        self.cancel_reason = CancellationReason(reason)

    def raise_if_cancelled(self):
        if self.cancel_reason is not None:
            raise asyncio.CancelledError(self.cancel_reason.value)
        if self.remaining <= 0:
            self.cancel_reason = CancellationReason.REQUEST_TIMEOUT
            raise asyncio.CancelledError(CancellationReason.REQUEST_TIMEOUT.value)

    def snapshot(self):
        return {
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "operation_id": self.operation_id,
            "deadline": self.deadline,
            "cancel_reason": self.cancel_reason.value if self.cancel_reason else None,
        }

    def detached_context(self):
        context = contextvars.Context()
        return context


def current_execution_context() -> RequestExecutionContext:
    context = current_execution.get()
    if context is None:
        raise NoRequestContextError("No LingShu request execution context is active")
    return context


def bind_execution_context(context: RequestExecutionContext):
    return _ExecutionBinding(context)


def current_deadline() -> float:
    return current_execution_context().deadline


def remaining_time() -> float:
    return current_execution_context().remaining


def cancel(reason: CancellationReason | str):
    current_execution_context().cancel(reason)


def raise_if_cancelled():
    current_execution_context().raise_if_cancelled()
