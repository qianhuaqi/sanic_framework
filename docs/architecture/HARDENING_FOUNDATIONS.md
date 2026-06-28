# LingShu Hardening Foundations

- Status: Proposed for P0-D5
- Decision Issue: #43
- Parent Issue: #25
- Related ADR: `docs/decisions/ADR-005-hardening-foundations.md`

## 1. Purpose

This document defines the implementation contract for:

- time and identifiers;
- framework errors and safe client responses;
- configuration sources, snapshots, reload, and rollback;
- serialization and content negotiation;
- Runtime Record events, storage, budgets, and recovery;
- common telemetry fields and redaction.

It does not create production code or select concrete third-party backends.

## 2. Time model

### Wall clock

Used for:

- human-readable logs;
- record timestamps;
- cross-process and cross-machine correlation;
- retention-age evaluation.

Format:

```text
RFC3339 UTC with trailing Z
```

### Monotonic clock

Used for:

- Deadline;
- timeout;
- queue wait;
- scheduling;
- duration;
- local event ordering.

Represent durations as integer nanoseconds where practical.

Rules:

- wall-clock changes never alter Deadline budgets;
- monotonic values never cross Worker/machine trust boundaries;
- each Runtime Record has its own increasing `event_sequence`;
- no global total event order is invented.

## 3. Identifier catalog

| Identifier | Width | Canonical text | Owner/lifetime |
|---|---:|---|---|
| RequestId | 128-bit | 32 lowercase hex | one Request Scope |
| ConnectionId | 128-bit | 32 lowercase hex | one accepted connection |
| TraceId | 128-bit | 32 lowercase hex | one distributed trace |
| OperationId | 128-bit | 32 lowercase hex | one child operation/span |
| WorkerId | 128-bit | 32 lowercase hex | one Worker process instance |
| RecordId | 128-bit | 32 lowercase hex | one logical Runtime Record |
| RevisionId | SHA-256 | 64 lowercase hex | one canonical Application Revision |

Runtime IDs use a cryptographically secure random source and carry no encoded meaning.

Typed wrappers prevent accidental interchange. A RequestId cannot be passed where a WorkerId is required merely because both contain strings.

## 4. Identifier trust boundary

### Internal Request ID

LingShu always generates a new internal RequestId before application handling.

Inbound `X-Request-ID`:

- is length/character validated;
- is stored only as `external_request_id`;
- never replaces the internal RequestId;
- is never used for authorization, storage paths, or uniqueness guarantees.

The response exposes the internal RequestId through `X-Request-ID`.

### Trace context

A valid remote trace context may continue a TraceId. This means correlation only, not trust. Invalid input is safely ignored or rejected under a separately configured strict policy.

### Outbound propagation

Outbound integrations may receive:

- trace propagation context;
- internal RequestId as a correlation header;
- OperationId for local diagnostics.

User, tenant, credential, or secret context is not propagated automatically.

## 5. Identifier validation

Canonical internal ID text accepts only:

```regex
^[0-9a-f]{32}$
```

Revision ID accepts only:

```regex
^[0-9a-f]{64}$
```

Validation is exact; uppercase, separators, whitespace, and alternative encodings are rejected for canonical internal representation.

External correlation values use a separate bounded validation policy and are never parsed as internal typed IDs.

## 6. Exception base contract

Ordinary framework failures inherit conceptually from `LingShuError` and expose structured metadata:

```text
code: stable dotted code
safe_message: client/log-safe summary
client_visible: bool
retryable: bool
http_status: optional integer
severity: debug|info|warning|error|critical
fatal_scope: operation|request|connection|worker|supervisor
safe_details: optional bounded mapping
internal_cause: private cause chain
```

Cancellation remains control flow and must not be swallowed by broad exception handlers.

## 7. Exception categories

### ConfigurationError

Schema, source, migration, secret, or reload preparation failure.

### LifecycleError

Illegal Application/Worker/Extension state transition or cleanup failure.

### ProtocolError

Malformed or ambiguous transport/HTTP framing handled at protocol boundaries.

### RequestError

Invalid request metadata/body or route body-policy violation.

### RoutingError

Not found, method not allowed, conflict, or invalid route definition.

### HandlerContractError

Invalid Handler signature, unsupported return, double call, or contract violation.

### SerializationError

Encode/decode/media-type/content-negotiation failure.

### ResourceLimitError

Configured size, count, memory, queue, or disk budget exceeded.

### AdmissionError

Work rejected or wait Deadline expired before execution.

### DeadlineError

An operation exhausted its inherited Deadline.

### ExtensionError

Extension dependency, contribution, startup, health, or cleanup failure.

### RecordError / StorageError

Runtime Record reservation, write, flush, retention, recovery, or backend failure.

### InternalError

Unexpected framework defect with safe external representation.

## 8. Error-code registry

Codes are stable lowercase dotted names:

```text
config.invalid
config.schema_mismatch
config.reload_failed
lifecycle.invalid_state
protocol.invalid_framing
request.invalid
request.body_too_large
route.not_found
route.method_not_allowed
handler.invalid_signature
handler.invalid_return
serialization.invalid_json
serialization.not_acceptable
serialization.unsupported_media_type
resource.capacity_exhausted
admission.timeout
deadline.exceeded
extension.start_failed
record.capacity_unavailable
record.write_failed
internal.error
```

Rules:

- one semantic condition has one code;
- wording changes do not require a code change;
- code reuse with different meaning is prohibited;
- new codes require contract tests and documentation;
- arbitrary exception messages are never metric dimensions.

## 9. Client problem response

Framework-generated client errors use:

```text
Content-Type: application/problem+json; charset=utf-8
```

Envelope:

```json
{
  "type": "urn:lingshu:error:<code>",
  "title": "Safe short title",
  "status": 400,
  "detail": "Safe user-facing explanation.",
  "instance": "urn:lingshu:request:<request_id>",
  "code": "<stable code>",
  "request_id": "<internal request id>",
  "details": {}
}
```

`details` is optional and schema-specific. It cannot contain secrets, raw bodies, credentials, stack traces, absolute paths, SQL, environment variables, internal addresses, or arbitrary exception text.

Unexpected failures emit `internal.error` and generic detail.

## 10. Cause and fatality handling

Internal cause chains preserve diagnostic relationships but pass through redaction before recording.

`retryable` means a retry might be technically safe; it does not trigger automatic retry.

`fatal_scope` determines escalation:

- operation: fail one child operation;
- request: fail/abort one request;
- connection: close one connection;
- worker: stop/restart one Worker under ADR-002;
- supervisor: terminate service after bounded cleanup.

## 11. Configuration source model

Precedence:

```text
built-in defaults
< file
< environment
< CLI
< explicit programmatic overrides
```

Each source yields a partial normalized mapping plus source metadata.

Merge rules:

- mapping values merge recursively by key;
- scalars replace lower-priority values;
- sequences replace; they do not concatenate implicitly;
- unknown keys fail by default;
- duplicate normalized keys within one source fail;
- type conversion follows the declared schema only;
- no source uses `eval` or arbitrary code execution.

## 12. Configuration schema and migration

File configuration declares `schema_version`.

A schema defines:

- field path;
- type;
- required/default behavior;
- allowed range/set;
- secret classification;
- reloadability;
- deprecation and migration rules;
- validation dependencies.

Version mismatch fails fast unless an explicit migration chain exists.

Migration requirements:

- exact source and target versions;
- deterministic output;
- no silent data loss;
- diagnostics for changed/deprecated fields;
- unit and golden tests;
- no migration of secret values into logs or diagnostics.

## 13. Secret handling

Secrets use a dedicated `SecretValue` or provider reference.

Required behavior:

- redacted `repr` and string conversion;
- excluded/masked in configuration dumps;
- never emitted into logs, traces, metrics, records, exceptions, or diagnostics;
- never inserted into Revision canonical material as plaintext;
- missing/unresolvable required secret prevents readiness;
- secret changes can affect Revision identity through a non-secret stable change token/provider version.

## 14. Immutable Configuration Snapshot

After validation, runtime code receives a typed immutable Snapshot.

The Snapshot includes:

```text
schema_version
revision_id
loaded_at
source_manifest
validated values
redaction metadata
reloadability metadata
```

Mutable parser dictionaries and environment views are discarded from runtime state.

## 15. Reload transaction

```text
LOAD
→ NORMALIZE
→ VALIDATE
→ RESOLVE SECRETS
→ PREPARE RESOURCES
→ COMPILE/FREEZE REVISION
→ ATOMIC PUBLISH
→ DRAIN OLD REVISION
→ CLEANUP OLD RESOURCES
```

Rules:

- no partial visibility before atomic publish;
- failure before publish leaves the old Revision untouched;
- failure after publish triggers safe rollback where possible;
- unsafe rollback produces explicit degraded/not-ready state;
- every attempt records old/new RevisionId, stage, outcome, and error code;
- multi-Worker partial rollout is never reported as success.

The transport used for multi-Worker coordination remains deferred.

## 16. Serializer registry

A serializer registration declares:

```text
name
media_types
supported value contract
encode
decode?
default charset
streaming capability
maximum limits
deterministic/canonical mode
```

The registry is compiled at Application freeze and immutable while running.

Baseline media types:

```text
text/plain; charset=utf-8
application/octet-stream
application/json; charset=utf-8
application/problem+json; charset=utf-8
```

## 17. Strict JSON input

JSON decoding:

- requires UTF-8;
- rejects unsupported charset declarations;
- rejects duplicate object keys;
- rejects NaN and Infinity;
- applies configured byte, depth, item, string, and numeric-token limits;
- accepts only JSON-defined values;
- reports location safely without echoing sensitive payload text;
- consumes the Request body under existing single-consumer and Deadline rules.

## 18. JSON output

Baseline supported values:

- `None` → `null`;
- bool;
- finite int/float within configured token limits;
- str;
- list/tuple-like approved sequence;
- mapping with string keys.

Explicit serializers are required for:

- datetime: RFC3339 UTC with `Z`;
- bytes: base64 under an explicit schema;
- Decimal;
- UUID-like/custom domain values.

Unknown objects fail instead of falling back to `repr`, `__dict__`, or arbitrary hooks.

Normal response encoding preserves mapping insertion order. Canonical mode sorts keys and normalizes separators only for hashing or deterministic record material.

## 19. Content negotiation

### Request side

- unsupported `Content-Type` → 415;
- missing required Content-Type for structured decode → 415;
- route policy determines body forbidden/optional/required/streamed/decoded;
- media-type parameters are parsed strictly.

### Response side

- absent `Accept` behaves as `*/*`;
- select by quality and specificity among registered representations;
- no acceptable representation → 406;
- emit explicit Content-Type;
- never use content sniffing.

Form, multipart, upload, compression, and streaming formats remain deferred.

## 20. Runtime Record reservation

Before Handler execution, admission reserves:

- RecordId;
- queue capacity;
- record/event budget;
- selected durability policy;
- required storage health.

Under `required` policy, failure rejects the request before business handling.

Under `best_effort`, the request may continue only while the record explicitly marks incomplete/drop state and health metrics reflect the loss.

Default business-request policy is `required`.

## 21. Runtime Record event envelope

```text
schema_version
record_id
request_id
connection_id?
trace_id?
operation_id?
worker_id
revision_id
event_type
event_sequence
wall_time
monotonic_ns
component
severity
outcome
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

Requirements:

- one schema version per envelope;
- event sequence strictly increases within a Record;
- attributes use allowlisted names and bounded values;
- body/header/query/cookie content is absent by default;
- approved payload capture uses bounded summaries or external references;
- truncation/drop information is explicit.

## 22. Default local writer

Storage uses rotated append-only UTF-8 JSON Lines segments.

Directory concept:

```text
<record_base>/
  manifest.json
  active/
  closed/
  quarantine/
```

Rules:

- framework-generated safe filenames only;
- canonical base-path containment validation;
- reject symlink traversal and unsafe ownership/permissions;
- one complete event per line;
- active segment append only;
- atomic manifest update with temporary file and rename;
- rotate by configured bytes/time/event count;
- closed segments become retention candidates;
- external backends attach through extension protocols.

## 23. Durability policy

```text
buffered: process buffer; possible tail loss
flush: flush userspace/runtime buffers at boundaries
fsync: request OS durability at configured boundaries
```

The selected level is included in health diagnostics. It never overstates guarantees.

Fsync frequency is bounded and configurable; per-event fsync is not assumed.

## 24. Budgets

Independent budgets exist for:

```text
max event bytes
max events per record
max record bytes
queue item count
queue byte count
active segment bytes
segment age
total storage bytes
retention age
cleanup items/time per cycle
flush deadline
shutdown flush deadline
recovery time/work
```

All limits produce explicit metrics and stable error codes.

## 25. Disk watermarks

### Normal

Full configured capture within limits.

### Soft watermark

- reduce optional detail;
- truncate approved payload summaries;
- accelerate retention cleanup;
- emit warning and capacity metrics.

### Hard watermark

- mark service not ready for `required` record policy;
- reject new audited business requests;
- preserve existing cleanup and minimal diagnostics.

### Critical reserve

- stop nonessential record writes;
- preserve health, shutdown, and data-loss diagnostics;
- protect filesystem/process stability.

Active segments are never removed by retention cleanup.

## 26. Retention

Retention deletes only closed, unreferenced segments that meet age and policy requirements.

Deletion is:

- bounded per cycle;
- recorded;
- safe under concurrent readers/exporters;
- paused when ownership/manifest state is uncertain;
- never based on user-controlled raw path data.

## 27. Crash recovery

Startup recovery:

1. obtain writer lock/lease;
2. validate storage root and permissions;
3. load manifest or rebuild from segments;
4. scan active tails;
5. discard/truncate only incomplete final lines;
6. validate required envelope fields and versions;
7. quarantine unrecoverable segments;
8. rebuild indexes/counters;
9. report recovery results and estimated loss;
10. become ready only if the configured policy can be honored.

Recovery has a Deadline and work limit. Exceeding them leaves the service not ready rather than hanging startup.

## 28. Common telemetry fields

Where applicable, structured logs, traces, diagnostic events, and Runtime Records use:

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

Missing concepts are omitted, not filled with fake values.

## 29. Metrics cardinality rules

Never use these as metric labels:

```text
request_id
record_id
trace_id
operation_id
connection_id
raw path
raw error message
user/tenant id by default
```

Permitted bounded dimensions include:

```text
component
route name/template
method
status class
outcome
stable error code
cancellation reason
worker role
```

Cardinality budgets apply to custom extension attributes.

## 30. Redaction classes

```text
public
internal
sensitive
secret
```

- public: safe for all configured outputs;
- internal: diagnostic only, never client-visible by default;
- sensitive: omitted, tokenized, hashed, or truncated only by explicit policy;
- secret: never emitted.

Sensitive by default:

- Authorization and Cookie headers;
- query values;
- body values;
- credentials/tokens;
- configuration secrets;
- SQL parameters;
- internal exception messages and paths.

One classification registry is shared across errors, logs, traces, Runtime Records, and diagnostics.

## 31. Required test matrix

### Time and identifiers

- secure random generation and failure;
- canonical text validation;
- type non-interchangeability;
- no semantic leakage;
- inbound Request ID cannot replace internal ID;
- valid/invalid trace propagation.

### Errors

- stable code registry;
- safe problem schema;
- most-specific mapping;
- cause redaction;
- fatal-scope escalation;
- cancellation remains control flow;
- no secret/traceback leakage.

### Configuration

- deterministic precedence;
- mapping/sequence merge rules;
- unknown/duplicate key failure;
- schema mismatch and migration;
- secret redaction;
- immutable Snapshot;
- reload success/failure/rollback/degraded state;
- no partial revision visibility.

### Serialization

- UTF-8 and charset handling;
- duplicate keys;
- NaN/Infinity rejection;
- size/depth/item/string/number limits;
- unsupported types;
- datetime/base64 explicit serializers;
- 406 and 415 paths;
- deterministic canonical output.

### Runtime Record

- reservation before Handler;
- queue/event/record budget saturation;
- required versus best-effort behavior;
- partial final line;
- damaged/missing manifest;
- permission/symlink/path traversal;
- disk-full and all watermarks;
- segment rotation and retention;
- recovery Deadline;
- quarantine behavior;
- shutdown flush and incomplete-record marking.

### Telemetry

- common field naming;
- correlation consistency;
- metric-cardinality enforcement;
- redaction across every output;
- no secret leakage under nested exceptions/failures.

## 32. Deferred decisions

- exact numeric defaults;
- configuration file syntax;
- secret-provider implementations;
- multi-Worker reload transport/consensus;
- form, multipart, upload, compression, and streaming serialization;
- concrete logger/metrics/tracing/exporter backends;
- OpenTelemetry package integration;
- cross-machine clock synchronization;
- public error-code compatibility guarantees after v1.0.

## 33. Acceptance rule

Merging the P0-D5 decision PR accepts ADR-005 and this contract. It still does not authorize production implementation. P1 remains blocked until the complete P0 Blueprint is frozen and the project lead explicitly authorizes P1.
