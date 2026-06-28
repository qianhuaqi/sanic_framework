# P0 Hardening Integration Verification

- Status: Proposed verification mapping for P0-D5
- Parent Issue: #25
- Decision Issue: #43
- Authoritative architecture: `docs/architecture/LINGSHU_FRAMEWORK_BLUEPRINT.md`
- Detailed hardening contract: `docs/architecture/HARDENING_FOUNDATIONS.md`

> This file is no longer an independent architecture checklist. It verifies where the original hardening topics are integrated. The Blueprint and accepted ADRs are authoritative.

## Integration mapping

### 1. Unified time model

Integrated by:

- ADR-002: absolute monotonic Deadline and duration semantics;
- ADR-005 proposal: UTC RFC3339 wall time, process-local monotonic time, per-record sequence, no cross-process monotonic comparison.

Verification:

- [x] system/wall time is not used for Deadline measurement;
- [x] monotonic time is used for timeout, queue wait, scheduling, and duration;
- [x] cross-process ordering does not invent a total order.

### 2. Standard identifiers

Integrated by ADR-005 proposal:

- RequestId;
- ConnectionId;
- TraceId;
- OperationId;
- WorkerId;
- RecordId;
- RevisionId.

Verification:

- [x] runtime IDs are typed, opaque, non-semantic, and unpredictable;
- [x] internal Request ID cannot be replaced by inbound correlation;
- [x] canonical text formats are explicit;
- [x] Revision ID is derived from canonical validated revision material.

### 3. Exception semantics

Integrated by ADR-004 and ADR-005 proposal.

Verification:

- [x] stable exception categories and error codes;
- [x] explicit client visibility and retryability;
- [x] fatal scope and severity;
- [x] safe problem response;
- [x] cause-chain and sensitive-data redaction;
- [x] cancellation is not converted into an ordinary error.

### 4. Configuration versioning

Integrated by ADR-004 freeze semantics and ADR-005 proposal.

Verification:

- [x] schema version and fail-fast mismatch;
- [x] explicit deterministic migration;
- [x] immutable typed Configuration Snapshot;
- [x] validate/prepare/freeze/publish/drain/cleanup reload flow;
- [x] no partial visibility;
- [x] rollback or explicit degraded state.

### 5. Serialization rules

Integrated by ADR-005 proposal.

Verification:

- [x] UTF-8 JSON baseline;
- [x] RFC3339 UTC datetime through explicit serializer;
- [x] bytes use base64 only through explicit schema/serializer;
- [x] null semantics explicit;
- [x] NaN/Infinity rejected;
- [x] duplicate JSON keys rejected;
- [x] parsing and encoding are bounded;
- [x] streaming formats remain explicitly deferred rather than guessed.

### 6. Async context isolation

Integrated by ADR-002 and ADR-004.

Verification:

- [x] Request/Operation Scope ownership;
- [x] request-created child tasks are request-owned;
- [x] detached background tasks clear request context;
- [x] context is cleared at Scope completion;
- [x] application singletons do not retain Request objects.

### 7. Telemetry standard fields

Integrated by ADR-002 and ADR-005 proposal.

Verification:

- [x] request/trace/operation/revision/worker correlation fields;
- [x] duration, status, outcome, error code, cancellation reason, and component;
- [x] shared redaction classification;
- [x] high-cardinality identifiers prohibited as metric labels;
- [x] attribute/label cardinality is bounded.

### 8. Worker and storage resource budgets

Integrated by ADR-002 and ADR-005 proposal.

Verification:

- [x] active requests and connections bounded;
- [x] event/record queue items and bytes bounded;
- [x] event/record/segment/total disk budgets;
- [x] soft, hard, and critical disk watermarks;
- [x] explicit backpressure or request rejection;
- [x] bounded retention, flush, shutdown, and crash recovery work.

## Freeze rule

This verification file is complete only after:

1. ADR-005 and `HARDENING_FOUNDATIONS.md` are reviewed and merged;
2. the Blueprint includes the accepted hardening section;
3. this status changes from Proposed to Verified;
4. no conflicting hardening specification remains active.

Until then, P1 remains blocked.
