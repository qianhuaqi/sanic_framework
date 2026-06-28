"""Deterministic immutable async Middleware chain compilation."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from lingshu.core.errors import FatalScope, HandlerContractError, LifecycleError
from lingshu.http.request import Request
from lingshu.http.response import Response
from lingshu.runtime import ScopeState


class Next(Protocol):
    """Single-use downstream call bound to one Request Scope and task."""

    def __call__(self) -> Awaitable[Response]:
        """Invoke the downstream chain exactly once."""
        ...


class Terminal(Protocol):
    """Already-normalized terminal callable used by a MiddlewarePlan."""

    def __call__(self, request: Request) -> Awaitable[Response]:
        """Return one Response for the bound Request."""
        ...


type MiddlewareCallable = Callable[[Request, Next], Awaitable[Response]]


class MiddlewareScope(StrEnum):
    """Compilation scope; Application and Route chains remain separate."""

    APPLICATION = "application"
    ROUTE = "route"


@dataclass(frozen=True, slots=True)
class MiddlewareDeclaration:
    """Immutable registration-time Middleware declaration."""

    callback: MiddlewareCallable
    priority: int = 0

    def __post_init__(self) -> None:
        if not callable(self.callback):
            raise TypeError("middleware callback must be callable")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise TypeError("middleware priority must be an integer")


@dataclass(frozen=True, slots=True)
class _MiddlewareEntry:
    declaration: MiddlewareDeclaration
    registration_sequence: int


class _NextState(StrEnum):
    CLAIMED = "claimed"
    CONSUMED = "consumed"
    FRESH = "fresh"
    INVALID = "invalid"
    RUNNING = "running"


class _NextCall:
    """Concrete immediate-claim Next implementation."""

    __slots__ = (
        "_awaitable",
        "_downstream",
        "_owner_task",
        "_request",
        "_state",
    )

    def __init__(
        self,
        request: Request,
        owner_task: asyncio.Task[object],
        downstream: Callable[[], Awaitable[Response]],
    ) -> None:
        self._request = request
        self._owner_task = owner_task
        self._downstream = downstream
        self._state = _NextState.FRESH
        self._awaitable: object | None = None

    def __call__(self) -> Awaitable[Response]:
        if self._state is _NextState.INVALID:
            raise _call_next_error(
                "middleware.call_next_inactive",
                "call_next is no longer active for this Middleware invocation.",
            )
        if self._state is not _NextState.FRESH:
            raise _call_next_error(
                "middleware.call_next_reused",
                "call_next may be invoked only once.",
            )
        if asyncio.current_task() is not self._owner_task:
            raise _call_next_error(
                "middleware.call_next_wrong_task",
                "call_next must be invoked by the Middleware task that received it.",
            )
        self._checkpoint()
        self._state = _NextState.CLAIMED
        awaitable = self._invoke()
        self._awaitable = awaitable
        return awaitable

    async def _invoke(self) -> Response:
        if asyncio.current_task() is not self._owner_task:
            self._state = _NextState.INVALID
            raise _call_next_error(
                "middleware.call_next_wrong_task",
                "call_next cannot execute in another task.",
            )
        if self._state is not _NextState.CLAIMED:
            raise _call_next_error(
                "middleware.call_next_inactive",
                "call_next is not active.",
            )
        self._state = _NextState.RUNNING
        try:
            self._checkpoint()
            response = await self._downstream()
            self._checkpoint()
            return _require_response(response)
        finally:
            if self._state is _NextState.RUNNING:
                self._state = _NextState.CONSUMED

    def invalidate(self) -> None:
        """Invalidate unconsumed access when its Middleware frame exits."""

        if self._state is _NextState.FRESH:
            self._state = _NextState.INVALID
            return
        if self._state is _NextState.CLAIMED:
            awaitable = self._awaitable
            if inspect.iscoroutine(awaitable):
                awaitable.close()
            self._state = _NextState.INVALID

    def _checkpoint(self) -> None:
        scope = self._request._scope
        if scope.state is not ScopeState.OPEN:
            raise _call_next_error(
                "middleware.call_next_inactive",
                "call_next cannot outlive its active Request Scope.",
            )
        scope.checkpoint()


@dataclass(frozen=True, slots=True, init=False)
class MiddlewarePlan:
    """Immutable deterministic Middleware execution plan."""

    scope: MiddlewareScope
    _entries: tuple[_MiddlewareEntry, ...]

    def __init__(
        self,
        scope: MiddlewareScope,
        entries: tuple[_MiddlewareEntry, ...],
    ) -> None:
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "_entries", entries)

    @property
    def declarations(self) -> tuple[MiddlewareDeclaration, ...]:
        return tuple(entry.declaration for entry in self._entries)

    async def run(self, request: Request, terminal: Terminal) -> Response:
        """Execute deterministic ingress and reverse egress around ``terminal``."""

        if not callable(terminal):
            raise TypeError("middleware terminal must be callable")
        _checkpoint_request(request)

        async def invoke(index: int) -> Response:
            _checkpoint_request(request)
            if index >= len(self._entries):
                return _require_response(await terminal(request))

            entry = self._entries[index]
            owner_task = asyncio.current_task()
            if owner_task is None:
                raise _call_next_error(
                    "middleware.task_required",
                    "Middleware execution requires an active asyncio task.",
                )
            call_next = _NextCall(
                request,
                owner_task,
                lambda: invoke(index + 1),
            )
            try:
                response = await entry.declaration.callback(request, call_next)
                return _require_response(response)
            finally:
                call_next.invalidate()

        return await invoke(0)


def compile_middleware(
    scope: MiddlewareScope,
    declarations: Iterable[MiddlewareDeclaration],
) -> MiddlewarePlan:
    """Validate and compile one immutable Application or Route chain."""

    if not isinstance(scope, MiddlewareScope):
        raise TypeError("middleware scope must be a MiddlewareScope")
    entries: list[_MiddlewareEntry] = []
    for sequence, declaration in enumerate(declarations):
        if not isinstance(declaration, MiddlewareDeclaration):
            raise TypeError(
                "middleware declarations must be MiddlewareDeclaration values"
            )
        if not _is_async_callable(declaration.callback):
            raise HandlerContractError(
                "middleware.async_required",
                "Middleware callbacks must be asynchronous in P1.",
                fatal_scope=FatalScope.WORKER,
            )
        entries.append(_MiddlewareEntry(declaration, sequence))
    entries.sort(
        key=lambda entry: (
            entry.declaration.priority,
            entry.registration_sequence,
        )
    )
    return MiddlewarePlan(scope, tuple(entries))


def _is_async_callable(callback: object) -> bool:
    if inspect.iscoroutinefunction(callback):
        return True
    call = getattr(callback, "__call__", None)
    return inspect.iscoroutinefunction(call)


def _checkpoint_request(request: Request) -> None:
    if request._scope.state is not ScopeState.OPEN:
        raise _call_next_error(
            "middleware.scope_inactive",
            "Middleware execution requires an active Request Scope.",
        )
    request._scope.checkpoint()


def _require_response(value: object) -> Response:
    if not isinstance(value, Response):
        raise HandlerContractError(
            "middleware.invalid_return",
            "Middleware and its terminal must return a Response.",
            fatal_scope=FatalScope.REQUEST,
        )
    return value


def _call_next_error(code: str, message: str) -> LifecycleError:
    return LifecycleError(
        code,
        message,
        fatal_scope=FatalScope.REQUEST,
    )


__all__ = (
    "MiddlewareCallable",
    "MiddlewareDeclaration",
    "MiddlewarePlan",
    "MiddlewareScope",
    "Next",
    "Terminal",
    "compile_middleware",
)
