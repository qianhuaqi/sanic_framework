"""Hierarchical runtime Scope ownership and managed cleanup."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from contextvars import ContextVar, Token, copy_context
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypeVar

from lingshu.core.errors import LifecycleError
from lingshu.core.time import MonotonicClock, SystemMonotonicClock
from lingshu.runtime.cancellation import (
    Cancellation,
    CancellationReason,
    CancellationToken,
)
from lingshu.runtime.deadline import Deadline, deadline_exceeded_error

_T = TypeVar("_T")
_CURRENT_SCOPE: ContextVar[Scope | None] = ContextVar("lingshu_current_scope", default=None)


class ScopeKind(StrEnum):
    """P1 ownership levels."""

    APPLICATION = "application"
    CONNECTION = "connection"
    REQUEST = "request"
    OPERATION = "operation"


class ScopeState(StrEnum):
    """Local Scope lifecycle."""

    OPEN = "open"
    CANCELLING = "cancelling"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class TaskFailure:
    """Visible failure from a managed child task."""

    name: str
    exception: Exception


@dataclass(frozen=True, slots=True)
class CleanupFailure:
    """Visible failure from a registered cleanup callback."""

    name: str
    exception: Exception


@dataclass(frozen=True, slots=True)
class CleanupReport:
    """Bounded close outcome."""

    timed_out: bool
    task_failures: tuple[TaskFailure, ...]
    cleanup_failures: tuple[CleanupFailure, ...]
    incomplete_tasks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _CleanupRegistration:
    name: str
    callback: Callable[[], Coroutine[Any, Any, None]]


_ALLOWED_CHILDREN = {
    ScopeKind.APPLICATION: frozenset({ScopeKind.CONNECTION}),
    ScopeKind.CONNECTION: frozenset({ScopeKind.REQUEST}),
    ScopeKind.REQUEST: frozenset({ScopeKind.OPERATION}),
    ScopeKind.OPERATION: frozenset({ScopeKind.OPERATION}),
}


class Scope:
    """Own child scopes, tasks, cancellation, Deadline, and cleanup."""

    kind: ScopeKind
    parent: Scope | None
    clock: MonotonicClock
    deadline: Deadline | None
    cleanup_budget_ns: int
    cancellation: CancellationToken
    state: ScopeState

    def __init__(
        self,
        kind: ScopeKind,
        *,
        parent: Scope | None = None,
        deadline: Deadline | None = None,
        clock: MonotonicClock | None = None,
        cleanup_budget_ns: int = 1_000_000_000,
    ) -> None:
        if cleanup_budget_ns < 0:
            raise ValueError("cleanup budget must be non-negative")
        if parent is None and kind is not ScopeKind.APPLICATION:
            raise ValueError("only an application Scope may be root")
        if parent is not None and kind not in _ALLOWED_CHILDREN[parent.kind]:
            raise ValueError(f"{parent.kind.value} Scope cannot own {kind.value} Scope")

        self.kind = kind
        self.parent = parent
        self.clock = clock or (parent.clock if parent is not None else SystemMonotonicClock())
        self.deadline = _effective_deadline(parent, deadline)
        if kind in {ScopeKind.REQUEST, ScopeKind.OPERATION} and self.deadline is None:
            raise ValueError(f"{kind.value} Scope requires a finite Deadline")
        self.cleanup_budget_ns = cleanup_budget_ns
        self.cancellation = CancellationToken()
        self.state = ScopeState.OPEN
        self._children: set[Scope] = set()
        self._tasks: dict[asyncio.Task[Any], str] = {}
        self._task_failures: list[TaskFailure] = []
        self._cleanups: list[_CleanupRegistration] = []
        self._cleanup_failures: list[CleanupFailure] = []
        self._close_lock = asyncio.Lock()
        self._close_report: CleanupReport | None = None
        self._context_token: Token[Scope | None] | None = None
        if parent is not None:
            parent._ensure_open()
            parent._children.add(self)

    @classmethod
    def application(
        cls,
        *,
        clock: MonotonicClock | None = None,
        deadline: Deadline | None = None,
        cleanup_budget_ns: int = 1_000_000_000,
    ) -> Scope:
        """Create the root Application Scope."""

        return cls(
            ScopeKind.APPLICATION,
            clock=clock,
            deadline=deadline,
            cleanup_budget_ns=cleanup_budget_ns,
        )

    @property
    def active_task_count(self) -> int:
        return len(self._tasks)

    @property
    def active_child_count(self) -> int:
        return len(self._children)

    @property
    def task_failures(self) -> tuple[TaskFailure, ...]:
        return tuple(self._task_failures)

    @property
    def cleanup_failures(self) -> tuple[CleanupFailure, ...]:
        return tuple(self._cleanup_failures)

    def create_child(
        self,
        kind: ScopeKind,
        *,
        deadline: Deadline | None = None,
        duration_ns: int | None = None,
        cleanup_budget_ns: int | None = None,
    ) -> Scope:
        """Create an owned child whose Deadline cannot exceed this Scope's budget."""

        self._ensure_open()
        if deadline is not None and duration_ns is not None:
            raise ValueError("provide deadline or duration_ns, not both")
        requested = deadline
        if duration_ns is not None:
            requested = Deadline.after(duration_ns, self.clock, parent=self.deadline)
        return Scope(
            kind,
            parent=self,
            deadline=requested,
            clock=self.clock,
            cleanup_budget_ns=(
                self.cleanup_budget_ns if cleanup_budget_ns is None else cleanup_budget_ns
            ),
        )

    def register_cleanup(
        self,
        name: str,
        callback: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Register one reverse-order async cleanup callback."""

        self._ensure_open()
        if not name:
            raise ValueError("cleanup name must not be empty")
        self._cleanups.append(_CleanupRegistration(name, callback))

    def spawn(self, coroutine: Coroutine[Any, Any, _T], *, name: str) -> asyncio.Task[_T]:
        """Create a managed child task carrying this Scope's context."""

        self._ensure_open()
        self.checkpoint()
        if not name:
            raise ValueError("task name must not be empty")
        context = copy_context()
        context.run(_CURRENT_SCOPE.set, self)
        task = asyncio.create_task(coroutine, name=name, context=context)
        self._tasks[task] = name
        task.add_done_callback(self._task_done)
        return task

    async def run(self, coroutine: Coroutine[Any, Any, _T], *, name: str) -> _T:
        """Run one managed operation within this Scope's remaining Deadline."""

        try:
            self.checkpoint()
        except BaseException:
            coroutine.close()
            raise
        task = self.spawn(coroutine, name=name)
        if self.deadline is None:
            return await task
        remaining = self.deadline.remaining_seconds(self.clock)
        if remaining <= 0:
            task.cancel(CancellationReason.REQUEST_DEADLINE.value)
            self.cancel(CancellationReason.REQUEST_DEADLINE)
            raise deadline_exceeded_error()
        try:
            async with asyncio.timeout(remaining):
                return await task
        except TimeoutError as exc:
            self.cancel(CancellationReason.REQUEST_DEADLINE)
            raise deadline_exceeded_error() from exc

    def checkpoint(self) -> None:
        """Preserve cancellation control flow and enforce the absolute Deadline."""

        self.cancellation.checkpoint()
        if self.deadline is not None and self.deadline.expired(self.clock):
            self.cancel(CancellationReason.REQUEST_DEADLINE)
            raise deadline_exceeded_error()

    def cancel(self, reason: CancellationReason) -> bool:
        """Cancel this Scope and propagate owner cancellation to descendants."""

        if self.state is ScopeState.CLOSED:
            return False
        changed = self.cancellation.cancel(reason)
        if not changed:
            return False
        self.state = ScopeState.CANCELLING
        cancellation = self.cancellation.state
        assert cancellation is not None
        self._propagate_cancellation(cancellation)
        return True

    async def close(self) -> CleanupReport:
        """Idempotently close all descendants, tasks, and cleanups within a hard budget."""

        async with self._close_lock:
            if self._close_report is not None:
                return self._close_report
            self.state = ScopeState.CLOSING
            if (self._children or self._tasks) and not self.cancellation.cancelled:
                self.cancel(_normal_close_reason(self.kind))
                self.state = ScopeState.CLOSING

            timed_out = False
            try:
                if self.cleanup_budget_ns == 0:
                    raise TimeoutError
                async with asyncio.timeout(self.cleanup_budget_ns / 1_000_000_000):
                    for child in tuple(self._children):
                        await child.close()
                    if self._tasks:
                        await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
                    for registration in reversed(self._cleanups):
                        await self._run_cleanup(registration)
            except TimeoutError:
                timed_out = True
                for task in tuple(self._tasks):
                    task.cancel("scope cleanup budget exhausted")

            incomplete = tuple(sorted(self._tasks.values()))
            self.state = ScopeState.CLOSED
            if self.parent is not None:
                self.parent._children.discard(self)
            self._close_report = CleanupReport(
                timed_out=timed_out,
                task_failures=tuple(self._task_failures),
                cleanup_failures=tuple(self._cleanup_failures),
                incomplete_tasks=incomplete,
            )
            return self._close_report

    async def __aenter__(self) -> Scope:
        self._ensure_open()
        if self._context_token is not None:
            raise LifecycleError("lifecycle.invalid_state", "Scope is already entered.")
        self._context_token = _CURRENT_SCOPE.set(self)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        del exc_type, exc, traceback
        token = self._context_token
        self._context_token = None
        if token is not None:
            _CURRENT_SCOPE.reset(token)
        await self.close()

    def _ensure_open(self) -> None:
        if self.state is not ScopeState.OPEN:
            raise LifecycleError(
                "lifecycle.invalid_state",
                "Scope is not open for new work.",
            )

    def _task_done(self, task: asyncio.Task[Any]) -> None:
        name = self._tasks.pop(task, task.get_name())
        if task.cancelled():
            return
        exception = task.exception()
        if isinstance(exception, Exception):
            self._task_failures.append(TaskFailure(name, exception))

    def _propagate_cancellation(self, cancellation: Cancellation) -> None:
        for child in tuple(self._children):
            if child.cancellation.cancel_from_parent(cancellation):
                child.state = ScopeState.CANCELLING
                child_state = child.cancellation.state
                assert child_state is not None
                child._propagate_cancellation(child_state)
        for task in tuple(self._tasks):
            task.cancel(cancellation.origin_reason.value)

    async def _run_cleanup(self, registration: _CleanupRegistration) -> None:
        cleanup_task: asyncio.Task[None] = asyncio.create_task(
            registration.callback(),
            name=f"cleanup:{registration.name}",
        )
        try:
            await asyncio.shield(cleanup_task)
        except asyncio.CancelledError:
            cleanup_task.cancel()
            await asyncio.gather(cleanup_task, return_exceptions=True)
            raise
        except Exception as exc:
            self._cleanup_failures.append(CleanupFailure(registration.name, exc))


def current_scope() -> Scope | None:
    """Return the Scope bound to the current context."""

    return _CURRENT_SCOPE.get()


def _effective_deadline(parent: Scope | None, requested: Deadline | None) -> Deadline | None:
    if parent is None:
        return requested
    if parent.deadline is None:
        return requested
    return Deadline.combine(parent.deadline, requested)


def _normal_close_reason(kind: ScopeKind) -> CancellationReason:
    if kind is ScopeKind.APPLICATION:
        return CancellationReason.APPLICATION_CANCELLED
    return CancellationReason.PARENT_CANCELLED


__all__ = (
    "CleanupFailure",
    "CleanupReport",
    "Scope",
    "ScopeKind",
    "ScopeState",
    "TaskFailure",
    "current_scope",
)
