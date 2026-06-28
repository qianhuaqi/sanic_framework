"""Runtime Record reservation composition helper."""

from __future__ import annotations

from collections.abc import Mapping

from lingshu.core.identifiers import (
    ConnectionId,
    OperationId,
    RecordId,
    RequestId,
    RevisionId,
    TraceId,
    WorkerId,
)
from lingshu.core.time import MonotonicClock, WallClock
from lingshu.record.model import (
    AttributeRule,
    RecordBudgets,
    RecordContext,
    RecordPolicy,
    RuntimeRecord,
)
from lingshu.record.queue import BoundedRecordQueue


def reserve_runtime_record(
    queue: BoundedRecordQueue,
    *,
    request_id: RequestId,
    worker_id: WorkerId,
    revision_id: RevisionId,
    policy: RecordPolicy = RecordPolicy.REQUIRED,
    connection_id: ConnectionId | None = None,
    trace_id: TraceId | None = None,
    operation_id: OperationId | None = None,
    budgets: RecordBudgets | None = None,
    attribute_rules: Mapping[str, AttributeRule] | None = None,
    wall_clock: WallClock | None = None,
    monotonic_clock: MonotonicClock | None = None,
) -> RuntimeRecord:
    """Generate RecordId and reserve queue capacity before business handling."""

    record_id = RecordId.generate()
    reservation = queue.reserve(record_id, policy)
    context = RecordContext(
        record_id=record_id,
        request_id=request_id,
        worker_id=worker_id,
        revision_id=revision_id,
        connection_id=connection_id,
        trace_id=trace_id,
        operation_id=operation_id,
    )
    return RuntimeRecord(
        context=context,
        reservation=reservation,
        policy=policy,
        budgets=budgets,
        attribute_rules=attribute_rules,
        wall_clock=wall_clock,
        monotonic_clock=monotonic_clock,
    )


__all__ = ("reserve_runtime_record",)
