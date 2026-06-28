from __future__ import annotations

from datetime import UTC, datetime

import pytest
from lingshu.core import RequestId, RevisionId, WorkerId
from lingshu.core.errors import RecordError, Severity
from lingshu.record import (
    AttributeMode,
    AttributeRule,
    BoundedRecordQueue,
    RecordBudgets,
    RecordPolicy,
    WatermarkState,
    reserve_runtime_record,
)


class Wall:
    def now(self) -> datetime:
        return datetime(2026, 6, 28, 12, 0, tzinfo=UTC)


class Mono:
    def __init__(self) -> None:
        self.value = 100

    def now_ns(self) -> int:
        self.value += 1
        return self.value


def ids() -> tuple[RequestId, WorkerId, RevisionId]:
    return RequestId.parse("a" * 32), WorkerId.parse("b" * 32), RevisionId.parse("c" * 64)


def test_reservation_event_sequence_and_envelope() -> None:
    request_id, worker_id, revision_id = ids()
    queue = BoundedRecordQueue(8, 100_000)
    record = reserve_runtime_record(
        queue,
        request_id=request_id,
        worker_id=worker_id,
        revision_id=revision_id,
        attribute_rules={"route": AttributeRule()},
        wall_clock=Wall(),
        monotonic_clock=Mono(),
    )
    first = record.append(
        "request.accepted",
        component="http",
        outcome="accepted",
        attributes={"route": "/users/{id}"},
    )
    second = record.append(
        "handler.completed",
        component="application",
        outcome="success",
        severity=Severity.INFO,
    )
    assert first is not None and second is not None
    assert (first.event_sequence, second.event_sequence) == (1, 2)
    assert first.to_dict()["record_id"] == str(record.context.record_id)
    assert first.wall_time == "2026-06-28T12:00:00Z"
    assert len(queue) == 2
    assert record.event_count == 2
    assert not record.incomplete
    record.close()
    assert not record.reservation.release()


def test_attributes_are_allowlisted_bounded_and_redacted() -> None:
    request_id, worker_id, revision_id = ids()
    queue = BoundedRecordQueue(8, 100_000)
    record = reserve_runtime_record(
        queue,
        request_id=request_id,
        worker_id=worker_id,
        revision_id=revision_id,
        attribute_rules={
            "public": AttributeRule(AttributeMode.PUBLIC, 64),
            "token": AttributeRule(AttributeMode.HASH, 64),
            "summary": AttributeRule(AttributeMode.TRUNCATE, 4),
            "secret": AttributeRule(AttributeMode.OMIT, 64),
        },
    )
    event = record.append(
        "request.metadata",
        component="record",
        outcome="captured",
        attributes={
            "public": {"count": 2},
            "token": "super-secret-token",
            "summary": "abcdef",
            "secret": "never-store-me",
        },
    )
    assert event is not None
    assert event.attributes["public"] == {"count": 2}
    assert event.attributes["token"] != "super-secret-token"
    assert event.attributes["summary"] == "abcd"
    assert "secret" not in event.attributes
    assert event.truncated
    rendered = event.to_json_line()
    assert b"super-secret-token" not in rendered
    assert b"never-store-me" not in rendered

    with pytest.raises(RecordError) as unknown:
        record.append(
            "request.invalid",
            component="record",
            outcome="rejected",
            attributes={"unknown": "value"},
        )
    assert unknown.value.code == "record.attribute_not_allowed"


def test_required_limits_raise_and_best_effort_exposes_loss() -> None:
    request_id, worker_id, revision_id = ids()
    required_queue = BoundedRecordQueue(1, 100_000)
    required = reserve_runtime_record(
        required_queue,
        request_id=request_id,
        worker_id=worker_id,
        revision_id=revision_id,
        budgets=RecordBudgets(
            max_event_bytes=1024,
            max_events_per_record=1,
            max_record_bytes=1024,
        ),
    )
    assert required.append("request.one", component="record", outcome="ok") is not None
    with pytest.raises(RecordError) as limit:
        required.append("request.two", component="record", outcome="ok")
    assert limit.value.code == "record.event_limit_exceeded"

    best_queue = BoundedRecordQueue(1, 100_000)
    best = reserve_runtime_record(
        best_queue,
        request_id=request_id,
        worker_id=worker_id,
        revision_id=revision_id,
        policy=RecordPolicy.BEST_EFFORT,
        budgets=RecordBudgets(
            max_event_bytes=1024,
            max_events_per_record=1,
            max_record_bytes=1024,
        ),
    )
    assert best.append("request.one", component="record", outcome="ok") is not None
    assert best.append("request.two", component="record", outcome="ok") is None
    assert best.incomplete
    assert best.dropped_events == 1


def test_queue_capacity_policy_and_watermark() -> None:
    request_id, worker_id, revision_id = ids()
    queue = BoundedRecordQueue(1, 128)
    first = reserve_runtime_record(
        queue,
        request_id=request_id,
        worker_id=worker_id,
        revision_id=revision_id,
    )
    with pytest.raises(RecordError) as full:
        reserve_runtime_record(
            queue,
            request_id=request_id,
            worker_id=worker_id,
            revision_id=revision_id,
        )
    assert full.value.code == "record.capacity_unavailable"

    best = reserve_runtime_record(
        queue,
        request_id=request_id,
        worker_id=worker_id,
        revision_id=revision_id,
        policy=RecordPolicy.BEST_EFFORT,
    )
    assert not best.reservation.available
    assert best.incomplete
    assert best.append("request.drop", component="record", outcome="lost") is None
    assert queue.dropped_events == 1

    first.close()
    queue.set_watermark(WatermarkState.HARD)
    with pytest.raises(RecordError):
        reserve_runtime_record(
            queue,
            request_id=request_id,
            worker_id=worker_id,
            revision_id=revision_id,
        )
