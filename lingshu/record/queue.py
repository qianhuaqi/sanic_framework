"""Bounded Runtime Record reservation and event queue."""

from __future__ import annotations

from collections import deque

from lingshu.core.errors import FatalScope, RecordError
from lingshu.core.identifiers import RecordId
from lingshu.record.model import RecordPolicy, WatermarkState


class QueueReservation:
    """Exactly-once queue reservation used by one RuntimeRecord."""

    __slots__ = ("_available", "_claimed", "_queue", "_record_id", "_released")

    def __init__(
        self,
        queue: BoundedRecordQueue,
        record_id: RecordId,
        *,
        available: bool,
    ) -> None:
        self._queue = queue
        self._record_id = record_id
        self._available = available
        self._claimed = False
        self._released = False

    @property
    def available(self) -> bool:
        return self._available and not self._released

    @property
    def record_id(self) -> RecordId:
        return self._record_id

    def submit(self, payload: bytes, policy: RecordPolicy) -> bool:
        """Consume reservation on first event, then use ordinary bounded capacity."""

        if self._released:
            return self._queue._drop(
                policy, "The Runtime Record reservation is closed."
            )
        if not self._available:
            return self._queue._drop(
                policy, "Runtime Record capacity was not reserved."
            )
        reserved = not self._claimed
        if reserved:
            self._queue._release_reserved_capacity()
            self._claimed = True
        return self._queue._submit(payload, policy)

    def release(self) -> bool:
        """Release unused reserved capacity exactly once."""

        if self._released:
            return False
        self._released = True
        if self._available and not self._claimed:
            self._queue._release_reserved_capacity()
        return True


class BoundedRecordQueue:
    """Single-loop bounded queue with independent item and byte limits."""

    def __init__(
        self,
        max_items: int,
        max_bytes: int,
        *,
        reservation_bytes: int = 1,
    ) -> None:
        if min(max_items, max_bytes, reservation_bytes) <= 0:
            raise ValueError("record queue limits must be positive")
        if reservation_bytes > max_bytes:
            raise ValueError("reservation_bytes cannot exceed max_bytes")
        self.max_items = max_items
        self.max_bytes = max_bytes
        self.reservation_bytes = reservation_bytes
        self._items: deque[bytes] = deque()
        self._queued_bytes = 0
        self._reserved_items = 0
        self._reserved_bytes = 0
        self._healthy = True
        self._watermark = WatermarkState.NORMAL
        self.dropped_events = 0

    @property
    def queued_bytes(self) -> int:
        return self._queued_bytes

    @property
    def reserved_items(self) -> int:
        return self._reserved_items

    @property
    def watermark(self) -> WatermarkState:
        return self._watermark

    @property
    def healthy(self) -> bool:
        return self._healthy

    def __len__(self) -> int:
        return len(self._items)

    def reserve(self, record_id: RecordId, policy: RecordPolicy) -> QueueReservation:
        """Reserve minimum queue capacity before business handling."""

        if not self._can_accept_required():
            if policy is RecordPolicy.REQUIRED:
                raise _record_error(
                    "record.capacity_unavailable",
                    "Runtime Record capacity is unavailable.",
                )
            return QueueReservation(self, record_id, available=False)
        if (
            len(self._items) + self._reserved_items >= self.max_items
            or self._queued_bytes + self._reserved_bytes + self.reservation_bytes
            > self.max_bytes
        ):
            if policy is RecordPolicy.REQUIRED:
                raise _record_error(
                    "record.capacity_unavailable",
                    "Runtime Record capacity is unavailable.",
                )
            return QueueReservation(self, record_id, available=False)
        self._reserved_items += 1
        self._reserved_bytes += self.reservation_bytes
        return QueueReservation(self, record_id, available=True)

    def pop(self) -> bytes | None:
        """Remove the oldest queued complete event payload."""

        if not self._items:
            return None
        payload = self._items.popleft()
        self._queued_bytes -= len(payload)
        return payload

    def restore_front(self, payload: bytes) -> None:
        """Restore a just-popped payload after a writer failure."""

        if not payload or not payload.endswith(b"\n") or payload.count(b"\n") != 1:
            raise ValueError("restored record payload must be one complete JSON line")
        if (
            len(self._items) >= self.max_items
            or self._queued_bytes + len(payload) > self.max_bytes
        ):
            raise RuntimeError("record queue restore would exceed configured capacity")
        self._items.appendleft(payload)
        self._queued_bytes += len(payload)

    def set_healthy(self, healthy: bool) -> None:
        self._healthy = healthy

    def set_watermark(self, watermark: WatermarkState) -> None:
        self._watermark = watermark

    def _submit(self, payload: bytes, policy: RecordPolicy) -> bool:
        if not payload or not payload.endswith(b"\n") or payload.count(b"\n") != 1:
            raise ValueError("record queue payload must be one complete JSON line")
        if not self._can_accept_required():
            return self._drop(policy, "Runtime Record storage is unavailable.")
        if (
            len(self._items) + self._reserved_items >= self.max_items
            or self._queued_bytes + self._reserved_bytes + len(payload) > self.max_bytes
        ):
            return self._drop(policy, "Runtime Record queue capacity is exhausted.")
        self._items.append(payload)
        self._queued_bytes += len(payload)
        return True

    def _drop(self, policy: RecordPolicy, message: str) -> bool:
        if policy is RecordPolicy.REQUIRED:
            raise _record_error("record.capacity_unavailable", message)
        self.dropped_events += 1
        return False

    def _can_accept_required(self) -> bool:
        return self._healthy and self._watermark not in {
            WatermarkState.HARD,
            WatermarkState.CRITICAL,
        }

    def _release_reserved_capacity(self) -> None:
        if self._reserved_items <= 0 or self._reserved_bytes < self.reservation_bytes:
            raise RuntimeError("record reservation accounting underflow")
        self._reserved_items -= 1
        self._reserved_bytes -= self.reservation_bytes


def _record_error(code: str, message: str) -> RecordError:
    return RecordError(code, message, fatal_scope=FatalScope.REQUEST, retryable=True)


__all__ = ("BoundedRecordQueue", "QueueReservation")
