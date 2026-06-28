from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from lingshu.core import RequestId, RevisionId, StorageError, WorkerId
from lingshu.record import (
    AttributeRule,
    BoundedRecordQueue,
    DurabilityMode,
    LocalRecordWriter,
    StorageWatermarks,
    WatermarkState,
    reserve_runtime_record,
)
from lingshu.runtime import Deadline


def make_payload(queue: BoundedRecordQueue) -> bytes:
    record = reserve_runtime_record(
        queue,
        request_id=RequestId.parse("a" * 32),
        worker_id=WorkerId.parse("b" * 32),
        revision_id=RevisionId.parse("c" * 64),
        attribute_rules={"key": AttributeRule()},
    )
    event = record.append(
        "request.accepted",
        component="record",
        outcome="success",
        attributes={"key": "value"},
    )
    assert event is not None
    payload = queue.pop()
    assert payload is not None
    return payload


def test_writer_appends_complete_lines_rotates_and_updates_manifest(tmp_path: Path) -> None:
    queue = BoundedRecordQueue(4, 100_000)
    payload = make_payload(queue)
    writer = LocalRecordWriter(
        tmp_path / "records",
        durability=DurabilityMode.FLUSH,
        segment_max_bytes=len(payload),
    )
    report = writer.start()
    assert report.recovered_events == 0
    writer.write(payload)
    assert writer.active_segment is None
    candidates = writer.retention_candidates()
    assert len(candidates) == 1
    assert candidates[0].read_bytes() == payload
    document = json.loads((writer.root / "manifest.json").read_text())
    assert document["active"] is None
    assert document["closed"] == [candidates[0].name]
    writer.close()

    reopened = LocalRecordWriter(writer.root)
    reopened.start(recover=False)
    assert [path.name for path in reopened.retention_candidates()] == [candidates[0].name]
    reopened.close()


def test_flush_queue_and_bounded_shutdown(tmp_path: Path) -> None:
    async def scenario() -> None:
        queue = BoundedRecordQueue(4, 100_000)
        record = reserve_runtime_record(
            queue,
            request_id=RequestId.parse("a" * 32),
            worker_id=WorkerId.parse("b" * 32),
            revision_id=RevisionId.parse("c" * 64),
        )
        assert record.append("request.one", component="record", outcome="ok")
        assert record.append("request.two", component="record", outcome="ok")
        writer = LocalRecordWriter(tmp_path / "records")
        writer.start()
        deadline = Deadline(writer.clock.now_ns() + 1_000_000_000)
        assert await writer.shutdown(queue, deadline=deadline) == 2
        assert not writer.started
        assert len(list((writer.root / "closed").glob("*.jsonl"))) == 1

        writer = LocalRecordWriter(tmp_path / "other")
        writer.start()
        expired = Deadline(writer.clock.now_ns())
        queue = BoundedRecordQueue(2, 100_000)
        record = reserve_runtime_record(
            queue,
            request_id=RequestId.parse("a" * 32),
            worker_id=WorkerId.parse("b" * 32),
            revision_id=RevisionId.parse("c" * 64),
        )
        assert record.append("request.one", component="record", outcome="ok")
        with pytest.raises(Exception) as timeout:
            await writer.flush_queue(queue, deadline=expired)
        assert timeout.value.code == "record.flush_timeout"
        writer.close()

    asyncio.run(scenario())


def test_recovery_truncates_partial_tail_and_quarantines_corruption(tmp_path: Path) -> None:
    root = tmp_path / "records"
    active = root / "active"
    active.mkdir(parents=True)
    valid_queue = BoundedRecordQueue(2, 100_000)
    valid = make_payload(valid_queue)
    (active / "segment-00000001.open.jsonl").write_bytes(valid + b'{"partial":')
    (active / "segment-00000002.open.jsonl").write_bytes(b'{"bad":true}\n')

    writer = LocalRecordWriter(root)
    report = writer.start()
    assert report.recovered_events == 1
    assert report.truncated_files == ("segment-00000001.open.jsonl",)
    assert report.quarantined_files == ("segment-00000002.open.jsonl.bad",)
    assert len(writer.retention_candidates()) == 1
    writer.close()


def test_writer_lock_symlink_and_watermarks(tmp_path: Path) -> None:
    root = tmp_path / "records"
    first = LocalRecordWriter(root)
    first.start()
    second = LocalRecordWriter(root)
    with pytest.raises(Exception) as locked:
        second.start()
    assert locked.value.code == "record.writer_locked"

    watermarks = StorageWatermarks(10, 20, 30)
    assert watermarks.state_for(0) is WatermarkState.NORMAL
    assert watermarks.state_for(10) is WatermarkState.SOFT
    assert watermarks.state_for(20) is WatermarkState.HARD
    assert watermarks.state_for(30) is WatermarkState.CRITICAL
    first.close()

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "linked-records"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links are unavailable")
    with pytest.raises(Exception) as unsafe:
        LocalRecordWriter(link).start()
    assert unsafe.value.code == "record.unsafe_path"


def test_flush_restores_event_when_writer_fails(tmp_path: Path) -> None:
    async def scenario() -> None:
        queue = BoundedRecordQueue(2, 100_000)
        record = reserve_runtime_record(
            queue,
            request_id=RequestId.parse("a" * 32),
            worker_id=WorkerId.parse("b" * 32),
            revision_id=RevisionId.parse("c" * 64),
        )
        assert record.append("request.one", component="record", outcome="ok")
        writer = LocalRecordWriter(tmp_path / "records", watermarks=StorageWatermarks(10, 20, 30))
        writer.start()
        writer.update_watermark(30)
        deadline = Deadline(writer.clock.now_ns() + 1_000_000_000)
        with pytest.raises(StorageError):
            await writer.flush_queue(queue, deadline=deadline)
        assert len(queue) == 1
        writer.close()

    asyncio.run(scenario())
