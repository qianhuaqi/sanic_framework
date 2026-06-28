from __future__ import annotations

from lingshu.core import RecordId
from lingshu.record import BoundedRecordQueue, RecordPolicy


def test_unused_reservation_releases_capacity_exactly_once() -> None:
    queue = BoundedRecordQueue(max_items=1, max_bytes=64)
    first = queue.reserve(RecordId.parse("a" * 32), RecordPolicy.REQUIRED)

    assert first.available
    assert queue.reserved_items == 1
    assert first.release()
    assert not first.release()
    assert queue.reserved_items == 0

    second = queue.reserve(RecordId.parse("b" * 32), RecordPolicy.REQUIRED)
    assert second.available
    assert queue.reserved_items == 1
    assert second.release()
    assert queue.reserved_items == 0
