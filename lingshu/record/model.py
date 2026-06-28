"""Runtime Record event, budget, and attribute contracts."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from lingshu.core.errors import FatalScope, RecordError, Severity
from lingshu.core.identifiers import (
    ConnectionId,
    OperationId,
    RecordId,
    RequestId,
    RevisionId,
    TraceId,
    WorkerId,
)
from lingshu.core.time import (
    MonotonicClock,
    SystemMonotonicClock,
    SystemWallClock,
    WallClock,
    format_rfc3339_utc,
)

_EVENT_TYPE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_COMPONENT = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")

type JSONScalar = str | int | float | bool | None
type JSONValue = JSONScalar | tuple[JSONValue, ...] | Mapping[str, JSONValue]


class RecordPolicy(StrEnum):
    """Whether loss is request-fatal or explicitly best-effort."""

    BEST_EFFORT = "best_effort"
    REQUIRED = "required"


class DurabilityMode(StrEnum):
    """Declared local-writer durability strength."""

    BUFFERED = "buffered"
    FLUSH = "flush"
    FSYNC = "fsync"


class WatermarkState(StrEnum):
    """Storage pressure state."""

    CRITICAL = "critical"
    HARD = "hard"
    NORMAL = "normal"
    SOFT = "soft"


class AttributeMode(StrEnum):
    """Per-key redaction action."""

    HASH = "hash"
    OMIT = "omit"
    PUBLIC = "public"
    TRUNCATE = "truncate"


@dataclass(frozen=True, slots=True)
class AttributeRule:
    """Allowlist and redaction rule for one event attribute."""

    mode: AttributeMode = AttributeMode.PUBLIC
    max_bytes: int = 256

    def __post_init__(self) -> None:
        if self.max_bytes <= 0:
            raise ValueError("attribute max_bytes must be positive")


@dataclass(frozen=True, slots=True)
class RecordBudgets:
    """Independent event and record limits."""

    max_event_bytes: int = 16_384
    max_events_per_record: int = 128
    max_record_bytes: int = 262_144
    max_attributes: int = 32
    max_attribute_depth: int = 4

    def __post_init__(self) -> None:
        if min(
            self.max_event_bytes,
            self.max_events_per_record,
            self.max_record_bytes,
            self.max_attributes,
            self.max_attribute_depth,
        ) <= 0:
            raise ValueError("record budgets must be positive")
        if self.max_event_bytes > self.max_record_bytes:
            raise ValueError("max_event_bytes cannot exceed max_record_bytes")


@dataclass(frozen=True, slots=True)
class RecordContext:
    """Stable correlation values shared by all events in one record."""

    record_id: RecordId
    request_id: RequestId
    worker_id: WorkerId
    revision_id: RevisionId
    connection_id: ConnectionId | None = None
    trace_id: TraceId | None = None
    operation_id: OperationId | None = None


@dataclass(frozen=True, slots=True)
class RecordEvent:
    """Immutable versioned Runtime Record event envelope."""

    schema_version: int
    record_id: RecordId
    request_id: RequestId
    worker_id: WorkerId
    revision_id: RevisionId
    event_type: str
    event_sequence: int
    wall_time: str
    monotonic_ns: int
    component: str
    severity: Severity
    outcome: str
    attributes: Mapping[str, JSONValue]
    truncated: bool
    connection_id: ConnectionId | None = None
    trace_id: TraceId | None = None
    operation_id: OperationId | None = None
    route_name: str | None = None
    http_method: str | None = None
    http_status: int | None = None
    error_code: str | None = None
    retryable: bool | None = None
    cancellation_reason: str | None = None
    duration_ns: int | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the bounded serialized envelope with absent optionals omitted."""

        document: dict[str, object] = {
            "schema_version": self.schema_version,
            "record_id": str(self.record_id),
            "request_id": str(self.request_id),
            "worker_id": str(self.worker_id),
            "revision_id": str(self.revision_id),
            "event_type": self.event_type,
            "event_sequence": self.event_sequence,
            "wall_time": self.wall_time,
            "monotonic_ns": self.monotonic_ns,
            "component": self.component,
            "severity": self.severity.value,
            "outcome": self.outcome,
            "attributes": _thaw_json(self.attributes),
            "truncated": self.truncated,
        }
        optional = {
            "connection_id": self.connection_id,
            "trace_id": self.trace_id,
            "operation_id": self.operation_id,
            "route_name": self.route_name,
            "http_method": self.http_method,
            "http_status": self.http_status,
            "error_code": self.error_code,
            "retryable": self.retryable,
            "cancellation_reason": self.cancellation_reason,
            "duration_ns": self.duration_ns,
        }
        for key, value in optional.items():
            if value is not None:
                document[key] = str(value) if key.endswith("_id") else value
        return document

    def to_json_line(self) -> bytes:
        """Encode one complete UTF-8 JSON Lines record."""

        return (
            json.dumps(
                self.to_dict(),
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )


class RuntimeRecord:
    """One reserved append-only record with strictly increasing event sequence."""

    def __init__(
        self,
        *,
        context: RecordContext,
        reservation: QueueReservationProtocol,
        policy: RecordPolicy,
        budgets: RecordBudgets | None = None,
        attribute_rules: Mapping[str, AttributeRule] | None = None,
        wall_clock: WallClock | None = None,
        monotonic_clock: MonotonicClock | None = None,
    ) -> None:
        self.context = context
        self.reservation = reservation
        self.policy = policy
        self.budgets = budgets or RecordBudgets()
        self.attribute_rules = MappingProxyType(dict(attribute_rules or {}))
        self.wall_clock = wall_clock or SystemWallClock()
        self.monotonic_clock = monotonic_clock or SystemMonotonicClock()
        self.event_count = 0
        self.record_bytes = 0
        self.incomplete = not reservation.available
        self.dropped_events = 0
        self.closed = False

    def append(
        self,
        event_type: str,
        *,
        component: str,
        outcome: str,
        severity: Severity = Severity.INFO,
        attributes: Mapping[str, object] | None = None,
        route_name: str | None = None,
        http_method: str | None = None,
        http_status: int | None = None,
        error_code: str | None = None,
        retryable: bool | None = None,
        cancellation_reason: str | None = None,
        duration_ns: int | None = None,
    ) -> RecordEvent | None:
        """Append one bounded event or explicitly expose best-effort loss."""

        if self.closed:
            raise _record_error("record.closed", "The Runtime Record is closed.")
        if _EVENT_TYPE.fullmatch(event_type) is None:
            raise ValueError("event_type must be a lowercase dotted identifier")
        if _COMPONENT.fullmatch(component) is None:
            raise ValueError("component must be a lowercase dotted identifier")
        if not outcome:
            raise ValueError("outcome must not be empty")
        if duration_ns is not None and duration_ns < 0:
            raise ValueError("duration_ns must be non-negative")
        if self.event_count >= self.budgets.max_events_per_record:
            return self._drop_or_raise(
                "record.event_limit_exceeded",
                "The Runtime Record event limit was exceeded.",
            )

        sanitized, truncated = sanitize_attributes(
            attributes or {},
            self.attribute_rules,
            max_attributes=self.budgets.max_attributes,
            max_depth=self.budgets.max_attribute_depth,
        )
        context = self.context
        event = RecordEvent(
            schema_version=1,
            record_id=context.record_id,
            request_id=context.request_id,
            worker_id=context.worker_id,
            revision_id=context.revision_id,
            event_type=event_type,
            event_sequence=self.event_count + 1,
            wall_time=format_rfc3339_utc(self.wall_clock.now()),
            monotonic_ns=self.monotonic_clock.now_ns(),
            component=component,
            severity=severity,
            outcome=outcome,
            attributes=sanitized,
            truncated=truncated,
            connection_id=context.connection_id,
            trace_id=context.trace_id,
            operation_id=context.operation_id,
            route_name=route_name,
            http_method=http_method,
            http_status=http_status,
            error_code=error_code,
            retryable=retryable,
            cancellation_reason=cancellation_reason,
            duration_ns=duration_ns,
        )
        payload = event.to_json_line()
        if len(payload) > self.budgets.max_event_bytes:
            return self._drop_or_raise(
                "record.event_too_large",
                "A Runtime Record event exceeds its configured limit.",
            )
        if self.record_bytes + len(payload) > self.budgets.max_record_bytes:
            return self._drop_or_raise(
                "record.record_too_large",
                "The Runtime Record exceeds its configured limit.",
            )
        if not self.reservation.submit(payload, self.policy):
            self.incomplete = True
            self.dropped_events += 1
            return None

        self.event_count += 1
        self.record_bytes += len(payload)
        return event

    def close(self) -> None:
        """Release any unused reservation and prevent future appends."""

        if self.closed:
            return
        self.closed = True
        self.reservation.release()

    def _drop_or_raise(self, code: str, message: str) -> None:
        if self.policy is RecordPolicy.REQUIRED:
            raise _record_error(code, message)
        self.incomplete = True
        self.dropped_events += 1
        return None


class QueueReservationProtocol(Protocol):
    """Structural reservation surface consumed by RuntimeRecord."""

    available: bool

    def submit(self, payload: bytes, policy: RecordPolicy) -> bool:
        """Submit a complete event line under the record policy."""
        ...

    def release(self) -> bool:
        """Release unused reservation capacity exactly once."""
        ...


def sanitize_attributes(
    attributes: Mapping[str, object],
    rules: Mapping[str, AttributeRule],
    *,
    max_attributes: int,
    max_depth: int,
) -> tuple[Mapping[str, JSONValue], bool]:
    """Allowlist, bound, redact, and freeze event attributes."""

    if len(attributes) > max_attributes:
        raise _record_error(
            "record.attribute_limit_exceeded",
            "The Runtime Record attribute limit was exceeded.",
        )
    result: dict[str, JSONValue] = {}
    truncated = False
    for key, raw_value in attributes.items():
        if not isinstance(key, str):
            raise _record_error(
                "record.attribute_invalid",
                "Runtime Record attribute keys must be strings.",
            )
        rule = rules.get(key)
        if rule is None:
            raise _record_error(
                "record.attribute_not_allowed",
                "A Runtime Record attribute is not allowlisted.",
            )
        if rule.mode is AttributeMode.OMIT:
            truncated = True
            continue
        value = _freeze_json(raw_value, depth=0, max_depth=max_depth)
        if rule.mode is AttributeMode.HASH:
            encoded = _canonical_json(value)
            result[key] = hashlib.sha256(encoded).hexdigest()
            truncated = True
        elif rule.mode is AttributeMode.TRUNCATE:
            if not isinstance(value, str):
                raise _record_error(
                    "record.attribute_invalid",
                    "A truncated Runtime Record attribute must be a string.",
                )
            shortened, changed = _truncate_utf8(value, rule.max_bytes)
            result[key] = shortened
            truncated = truncated or changed
        else:
            if len(_canonical_json(value)) > rule.max_bytes:
                raise _record_error(
                    "record.attribute_too_large",
                    "A Runtime Record attribute exceeds its configured limit.",
                )
            result[key] = value
    return MappingProxyType(result), truncated


def _freeze_json(value: object, *, depth: int, max_depth: int) -> JSONValue:
    if depth > max_depth:
        raise _record_error(
            "record.attribute_depth_exceeded",
            "A Runtime Record attribute exceeds its nesting limit.",
        )
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _record_error(
                "record.attribute_invalid",
                "Runtime Record attributes cannot contain non-finite numbers.",
            )
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise _record_error(
                    "record.attribute_invalid",
                    "Nested Runtime Record attribute keys must be strings.",
                )
            frozen[key] = _freeze_json(item, depth=depth + 1, max_depth=max_depth)
        return MappingProxyType(frozen)
    if isinstance(value, list | tuple):
        return tuple(
            _freeze_json(item, depth=depth + 1, max_depth=max_depth)
            for item in value
        )
    raise _record_error(
        "record.attribute_invalid",
        "A Runtime Record attribute has an unsupported value type.",
    )


def _canonical_json(value: JSONValue) -> bytes:
    return json.dumps(
        _thaw_json(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _thaw_json(value: JSONValue) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _truncate_utf8(value: str, max_bytes: int) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value, False
    shortened = encoded[:max_bytes]
    while shortened:
        try:
            return shortened.decode("utf-8"), True
        except UnicodeDecodeError:
            shortened = shortened[:-1]
    return "", True


def _record_error(code: str, message: str) -> RecordError:
    return RecordError(code, message, fatal_scope=FatalScope.REQUEST)


__all__ = (
    "AttributeMode",
    "AttributeRule",
    "DurabilityMode",
    "JSONScalar",
    "JSONValue",
    "QueueReservationProtocol",
    "RecordBudgets",
    "RecordContext",
    "RecordEvent",
    "RecordPolicy",
    "RuntimeRecord",
    "WatermarkState",
    "sanitize_attributes",
)
