# ADR-005: Identifiers, errors, configuration, serialization, Runtime Record, and telemetry

- Status: Accepted
- Date: 2026-06-28
- Parent architecture Issue: #25
- Decision Issue: #43 (completed)
- Implemented by: PR #44
- Effective merge commit: `704146f103e2daafac7e489951497411821e9ba9`
- Detailed model: `docs/architecture/HARDENING_FOUNDATIONS.md`

## Context

LingShu required one coherent hardening contract before production implementation. Identifiers, errors, configuration, serialization, Runtime Record storage, and telemetry are cross-cutting foundations; allowing each component to invent its own rules would create incompatible behavior and unsafe failure paths.

## Decision

### Unified time model

LingShu uses two clocks with separate purposes:

- UTC wall-clock time for human-readable timestamps, retention age, and cross-process correlation;
- monotonic time for Deadline, timeout, scheduling, queue wait, duration, and process-local ordering.

Wall timestamps use RFC3339 UTC with a trailing `Z`. Durations use integer nanoseconds where practical. Monotonic values are never compared across Workers or machines. Runtime Records use a strictly increasing per-record event sequence rather than fabricating a global total order.

### Typed identifiers

LingShu defines:

```text
RequestId     128-bit / 32 lowercase hexadecimal characters
ConnectionId  128-bit / 32 lowercase hexadecimal characters
TraceId       128-bit / 32 lowercase hexadecimal characters
OperationId   128-bit / 32 lowercase hexadecimal characters
WorkerId      128-bit / 32 lowercase hexadecimal characters
RecordId      128-bit / 32 lowercase hexadecimal characters
RevisionId    SHA-256 / 64 lowercase hexadecimal characters
```

Runtime identifiers are opaque, non-semantic, immutable, and generated with a cryptographically secure source. They do not encode time, host, PID, user, tenant, route, or business meaning. Typed identifiers are not interchangeable.

LingShu always generates its own internal RequestId. An inbound `X-Request-ID` is validated and retained only as untrusted external correlation; it never replaces the internal ID or participates in authorization or storage-path construction.

A valid remote trace context may continue trace correlation but does not establish trust or authorization.

### Exception taxonomy

`LingShuError` is the conceptual root for ordinary framework failures. Stable categories include:

```text
ConfigurationError
LifecycleError
ProtocolError
RequestError
RoutingError
HandlerContractError
SerializationError
ResourceLimitError
AdmissionError
DeadlineError
ExtensionError
RecordError
StorageError
InternalError
```

Cancellation remains control flow governed by ADR-002 and is not converted into an ordinary framework error by broad exception handling.

Every framework error conceptually carries:

```text
code
safe_message
client_visible
retryable
http_status?
severity
fatal_scope
safe_details?
internal_cause?
```

`fatal_scope` is one of operation, request, connection, worker, or supervisor.

### Stable error codes and safe client output

Framework error codes are stable lowercase dotted identifiers, such as:

```text
config.invalid
lifecycle.invalid_state
request.body_too_large
route.not_found
handler.invalid_return
serialization.invalid_json
resource.capacity_exhausted
record.storage_unavailable
internal.error
```

Client-visible framework errors use `application/problem+json` and expose only allowlisted safe fields, including stable code and internal RequestId.

Default client output never exposes traceback, arbitrary exception text, source code, absolute paths, environment values, configuration values, credentials, secrets, SQL, request bodies, or internal topology.

Unexpected failures map to `internal.error` with a generic client message. Internal causes are retained only through redacted diagnostic paths.

### Configuration sources and precedence

Configuration precedence is:

```text
built-in defaults
< configuration file
< environment variables
< CLI overrides
< explicit programmatic overrides
```

Rules:

- all values are normalized and validated through a declared schema;
- unknown keys fail by default;
- duplicate normalized keys within one source fail;
- nested mappings merge by key;
- scalar and sequence values replace lower-priority values;
- environment parsing is schema-driven and never uses `eval`;
- file configuration declares a schema version;
- version mismatch fails unless an explicit deterministic migration exists;
- migrations are testable and never silently lossy.

The exact configuration file syntax remains deferred.

### Secrets and immutable configuration snapshots

Secrets use a dedicated secret value or provider reference.

- secret representation is redacted everywhere;
- secrets are excluded or masked in configuration dumps;
- secrets are never emitted through logs, traces, metrics, records, errors, or diagnostics;
- plaintext secrets are not inserted into Revision hashing;
- missing required secrets prevent readiness.

Runtime components receive an immutable typed Configuration Snapshot rather than mutable parser dictionaries or live environment views.

### Revision-based reload and rollback

Reload follows:

```text
load
→ normalize
→ validate
→ resolve secrets
→ prepare resources
→ compile/freeze new Revision
→ publish atomically
→ drain old Revision
→ cleanup old resources
```

Failure before publication leaves the current Revision unchanged. Post-publication failure rolls back when safe; otherwise the service enters an explicit degraded/not-ready state and records the divergence. No component may observe a partially applied configuration. A partial multi-Worker rollout is never reported as success.

The multi-Worker coordination transport remains deferred.

### Serialization registry

Serialization is explicit and media-type based. Baseline representations are:

```text
text/plain; charset=utf-8
application/octet-stream
application/json; charset=utf-8
application/problem+json; charset=utf-8
```

Serializers declare supported values, media types, encode/decode behavior, safety limits, and determinism characteristics. Arbitrary object introspection is not a wire contract.

### Strict JSON

LingShu JSON behavior is strict and bounded:

- UTF-8 only;
- no BOM on output;
- duplicate object keys rejected on input;
- NaN and positive/negative infinity rejected on input and output;
- byte size, depth, container count, string length, and numeric token length bounded;
- unknown Python objects rejected;
- `None` maps to JSON `null`;
- string-keyed mappings and JSON-native finite values supported;
- datetime uses RFC3339 UTC only through an explicit serializer;
- bytes use base64 only through an explicit schema/serializer;
- Decimal and domain values require explicit serializers;
- ordinary response JSON preserves mapping insertion order;
- canonical sorted-key encoding is reserved for hashing and deterministic record material.

### Content negotiation

Request decoding:

- unsupported media type produces 415;
- required structured decoding without Content-Type produces 415;
- media-type parameters are parsed strictly;
- route body policy decides whether a body is forbidden, optional, required, streamed, or decoded.

Response selection:

- absent `Accept` behaves as `*/*`;
- quality and specificity select a registered representation;
- no acceptable representation produces 406;
- Content-Type is explicit;
- content sniffing is prohibited.

Form, multipart, upload, compression, and streaming serialization remain deferred.

### Runtime Record reservation

Every admitted business request reserves a RecordId, queue capacity, record/event budget, durability policy, and required storage health before Handler execution.

Default business-request policy is `required`: if a Runtime Record cannot be reserved or safely queued, the request is rejected before business handling. The framework never reports complete auditability after reservation or write failure.

A separately declared `best_effort` policy may continue service only while explicitly recording loss/incompleteness and exposing health metrics.

### Runtime Record event envelope

Every versioned append-only event contains at least:

```text
schema_version
event_type
event_sequence
wall_time
monotonic_ns
component
severity
outcome
record_id
request_id
connection_id?
trace_id?
operation_id?
worker_id
revision_id
route_name?
http_method?
http_status?
error_code?
retryable?
cancellation_reason?
duration_ns?
attributes
truncated
```

Event sequence increases strictly inside one Record. Attributes are allowlisted, bounded, and redacted. Bodies and arbitrary objects are not embedded by default.

### Default local storage

The default local writer uses versioned UTF-8 JSON Lines in append-only rotated segment files.

- one complete event per line;
- incomplete crash-tail lines are discarded/truncated during recovery;
- active and closed segment state is tracked by an atomic manifest/index;
- manifest updates use temporary-file write, flush, and atomic rename where supported;
- filenames are framework-generated from safe internal values;
- all paths remain under a configured canonical base directory;
- symlink traversal, path traversal, and unsafe ownership/permissions are rejected;
- database and object-storage exporters remain optional extensions.

### Durability, budgets, and disk safety

Declared durability policies are:

```text
buffered
flush
fsync
```

Each policy reports only the durability it actually provides.

Independent limits cover event bytes, record bytes/count, queue items/bytes, segment bytes/age, total storage, retention, cleanup work, flush time, shutdown flush, and recovery work/time.

Disk states:

```text
normal
→ soft watermark
→ hard watermark
→ critical reserve
```

At soft watermark the framework reduces optional detail, truncates approved summaries, accelerates cleanup, and reports warning health. At hard watermark it marks not-ready and rejects new `required` business requests. Critical reserve preserves only minimal failure, health, and shutdown diagnostics while protecting filesystem stability.

Retention deletes only closed, unreferenced segments that satisfy policy. Active segments are never removed by retention cleanup.

### Crash recovery

Startup recovery:

1. acquire writer lock/lease;
2. validate storage path and permissions;
3. load or rebuild manifest;
4. scan active tails;
5. truncate incomplete final lines;
6. validate envelope versions and required fields;
7. quarantine unrecoverable segments rather than silently deleting them;
8. rebuild indexes and counters;
9. report recovered, truncated, quarantined, and estimated lost events;
10. become ready only when the configured record policy can be honored.

Recovery is bounded by work and time budgets. Exceeding them leaves the service not-ready rather than hanging startup indefinitely.

### Telemetry common fields

Structured logs, traces, diagnostics, and Runtime Records share names where applicable:

```text
timestamp
component
event
severity
outcome
framework_version
revision_id
worker_id
connection_id
request_id
record_id
trace_id
operation_id
route_name
http_method
http_status
error_code
retryable
cancellation_reason
duration_ns
```

Non-applicable fields are omitted rather than filled with misleading values.

### Redaction and metric cardinality

One classification is shared by all observability paths:

```text
public
internal
sensitive
secret
```

Secret values are never emitted. Sensitive values are omitted, hashed, tokenized, or truncated only by explicit policy. Authorization, Cookie, query/body values, credentials, tokens, configuration secrets, SQL parameters, and internal exception messages/paths are sensitive by default.

The following are prohibited as metric labels:

```text
request_id
record_id
trace_id
operation_id
connection_id
raw path
raw exception message
user or tenant ID by default
```

Metrics use bounded dimensions such as component, route name/template, method, status class, outcome, stable error code, and cancellation reason.

## Required acceptance tests

Implementation must test:

- secure identifier generation, canonical form, typed non-interchangeability, and generator failure;
- inbound correlation validation and protection of internal IDs;
- stable error-code registry and safe problem responses;
- cause-chain redaction and cancellation preservation;
- deterministic configuration precedence and unknown-key failure;
- schema migrations, secret redaction, immutable snapshots, reload, rollback, and degraded state;
- strict JSON duplicate-key, non-finite-number, limit, and unsupported-type behavior;
- 406 and 415 negotiation paths;
- Runtime Record reservation before Handler execution;
- required/best-effort queue saturation behavior;
- damaged manifest, partial line, permission, symlink, disk-full, watermark, retention, and recovery cases;
- common telemetry fields and metric-cardinality enforcement;
- no secret leakage through any output path.

## Rejected alternatives

- wall clock for Deadline measurement;
- trusting inbound Request IDs as internal IDs;
- semantic or sequential guessable runtime IDs;
- raw exception/traceback exposure;
- mutable runtime configuration dictionaries;
- partial in-place reload;
- silent schema migration;
- arbitrary-object JSON serialization;
- permissive NaN/Infinity or duplicate JSON keys;
- unbounded record queues or disk use;
- deleting active record segments during retention;
- claiming complete audit after reservation/write failure;
- using high-cardinality IDs as metric labels.

## Intentionally deferred

- exact numeric defaults and retention periods;
- configuration file syntax and secret-provider implementations;
- multi-Worker reload transport and consensus;
- form, multipart, upload, compression, and streaming formats;
- concrete logging, metrics, tracing, database, and object-storage backends;
- official OpenTelemetry integration;
- cross-machine clock synchronization;
- post-v1.0 error-code compatibility policy.
