"""Cancellation reasons and control-flow token."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum


class CancellationReason(StrEnum):
    """Frozen runtime cancellation taxonomy."""

    ADMISSION_REJECTED = "admission_rejected"
    APPLICATION_CANCELLED = "application_cancelled"
    CLIENT_DISCONNECT = "client_disconnect"
    DEPENDENCY_CANCELLED = "dependency_cancelled"
    PARENT_CANCELLED = "parent_cancelled"
    REQUEST_DEADLINE = "request_deadline"
    SERVER_DRAINING = "server_draining"
    WORKER_STOPPING = "worker_stopping"


@dataclass(frozen=True, slots=True)
class Cancellation:
    """One immutable first-writer-wins cancellation state."""

    reason: CancellationReason
    origin_reason: CancellationReason


class ScopeCancelled(asyncio.CancelledError):
    """Runtime control flow carrying an explicit cancellation reason."""

    def __init__(self, cancellation: Cancellation) -> None:
        self.cancellation = cancellation
        super().__init__(cancellation.reason.value)


class CancellationToken:
    """Idempotent cancellation state and async notification."""

    __slots__ = ("_event", "_state")

    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._state: Cancellation | None = None

    @property
    def cancelled(self) -> bool:
        return self._state is not None

    @property
    def state(self) -> Cancellation | None:
        return self._state

    def cancel(
        self,
        reason: CancellationReason,
        *,
        origin_reason: CancellationReason | None = None,
    ) -> bool:
        """Publish cancellation once and return whether this call won."""

        if self._state is not None:
            return False
        self._state = Cancellation(reason, origin_reason or reason)
        self._event.set()
        return True

    def cancel_from_parent(self, parent: Cancellation) -> bool:
        """Translate owner cancellation to the child taxonomy."""

        return self.cancel(
            CancellationReason.PARENT_CANCELLED,
            origin_reason=parent.origin_reason,
        )

    async def wait(self) -> Cancellation:
        """Wait until cancellation and return the published state."""

        await self._event.wait()
        assert self._state is not None
        return self._state

    def checkpoint(self) -> None:
        """Raise cancellation control flow when cancellation was published."""

        if self._state is not None:
            raise ScopeCancelled(self._state)


__all__ = (
    "Cancellation",
    "CancellationReason",
    "CancellationToken",
    "ScopeCancelled",
)
