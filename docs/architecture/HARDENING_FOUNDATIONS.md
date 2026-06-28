# LingShu Hardening Foundations

- Status: Accepted through P0-D5
- Decision Issue: #43 (completed)
- Pull Request: #44
- Effective merge commit: `704146f103e2daafac7e489951497411821e9ba9`
- Parent Issue: #25
- Related ADR: `docs/decisions/ADR-005-hardening-foundations.md`

## 1. Time contract

LingShu separates wall-clock and monotonic time:

- RFC3339 UTC wall time with trailing `Z` for human-readable timestamps, retention, and cross-process correlation;
- process-local monotonic time for Deadline, timeout, queue wait, scheduling, and duration;
- integer nanoseconds for durations where practical;
- strictly increasing `event_sequence` within one Runtime Record;
- no cross-Worker comparison of monotonic values and no fabricated global total order.

## 2. Identifier contract

```text
RequestId     128-bit / 32 lowercase hex
ConnectionId  128-bit / 32 lowercase hex
TraceId       128-bit / 32 lowercase hex
OperationId   128-bit / 32 lowercase hex
WorkerId      128-bit / 32 lowercase hex
RecordId      128-bit / 32 lowercase hex
RevisionId    SHA-256 / 64 lowercase hex
```

Runtime IDs use a cryptographically secure source and are opaque, immutable, non-semantic typed values. They do not encode timestamps, host, PID, user, tenant, route, or business data.

LingShu always creates its own internal RequestId. Inbound `X-Request-ID` is retained only as validated external correlation. It cannot replace the internal ID or influence authorization, uniqueness, or file paths.

A remote TraceId may continue valid distributed correlation but does not establish trust.

## 3. Framework error contract

Ordinary framework failures conceptually inherit from `LingShuError` and use stable categories:

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

Cancellation remains runtime control flow and is not absorbed into this hierarchy by broad handlers.

Each error carries:

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

Fatal scope is operation, request, connection, worker, or supervisor.

## 4. Stable error codes

Error codes are lowercase dotted identifiers, for example:

```text
config.invalid
config.schema_mismatch
config.reload_failed
lifecycle.invalid_state
protocol.invalid_framing
request.body_too_large
route.not_found
route.method_not_allowed
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

One semantic condition has one code. Wording can change without changing the code. Reusing a code for a different meaning is prohibited.

## 5. Safe client-error envelope

Framework-generated client errors use:

```text
application/problem+json; charset=utf-8
```

Conceptual envelope:

```json
{
  "type": "urn:lingshu:error:<code>",
  "title": "Safe short title",
  "status": 400,
  "detail": "Safe explanation.",
  "instance": "urn:lingshu:request:<request_id>",
  "code": "<stable code>",
  "request_id": "<internal request id>",
  "details": {}
}
```

`details` is optional, bounded, schema-defined, and redacted. Tracebacks, exception repr, source, absolute paths, environment/configuration values, credentials, secrets, SQL, request bodies, and internal topology are not client-visible by default.

Unexpected failures map to `internal.error` with a generic detail.

## 6. Configuration sources

Precedence is deterministic:

```text
built-in defaults
< configuration file
< environment variables
< CLI overrides
< explicit programmatic overrides
```

Rules:

- schema-based normalization and validation;
- unknown keys fail by default;
- duplicate normalized keys in one source fail;
- nested mappings merge by key;
- scalar and sequence values replace lower-priority values;
- environment parsing never uses `eval`;
- configuration files declare a schema version;
- schema mismatch fails unless an explicit migration exists;
- migration is version-to-version, deterministic, testable, and non-lossy unless explicitly rejected.

Configuration file syntax remains deferred.

## 7. Secrets and snapshots

Secrets use a dedicated value or provider reference.

Required behavior:

- redacted representation and diagnostics;
- exclusion/masking in configuration dumps;
- no emission through logs, traces, metrics, Runtime Records, errors, or diagnostics;
- no plaintext inclusion in Revision canonical material;
- required secret resolution before readiness.

Runtime components receive an immutable typed Configuration Snapshot with schema version, RevisionId, source manifest, validated values, and redaction/reload metadata. Mutable parser dictionaries and live environment views are not runtime configuration.

## 8. Reload transaction

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

No partial state is visible before publication. Pre-publication failure leaves the current Revision unchanged. Post-publication failure safely rolls back when possible; otherwise the service enters explicit degraded/not-ready state. Every attempt records old/new RevisionId, stage, outcome, and error code. Partial multi-Worker rollout is never success.

## 9. Serializer registry

Serializer registrations are compiled during Application freeze and remain immutable while running. A serializer declares media types, supported value contract, encode/decode behavior, default charset, streaming capability, limits, and deterministic/canonical mode.

Baseline media types:

```text
text/plain; charset=utf-8
application/octet-stream
application/json; charset=utf-8
application/problem+json; charset=utf-8
```

## 10. Strict JSON

Input and output rules:

- UTF-8 only;
- no output BOM;
- duplicate object keys rejected;
- NaN and Infinity rejected;
- byte, depth, item, string, and numeric-token limits;
- unknown objects rejected rather than using `repr`, `__dict__`, or arbitrary hooks;
- `None` maps to JSON `null`;
- JSON-native finite values and string-keyed mappings supported;
- datetime requires explicit RFC3339 UTC serializer;
- bytes require explicit base64 schema/serializer;
- Decimal and domain values require explicit serializers;
- ordinary encoding preserves mapping order;
- canonical sorted-key encoding is reserved for hashing and deterministic record material.

Decode errors report safe location data without echoing sensitive payload text.

## 11. Content negotiation

Request side:

- unsupported Content-Type produces 415;
- missing required Content-Type for structured decoding produces 415;
- media-type parameters are strict;
- route policy decides whether the body is forbidden, optional, required, streamed, or decoded.

Response side:

- missing Accept behaves as `*/*`;
- quality and specificity select a registered representation;
- no acceptable representation produces 406;
- Content-Type is explicit;
- content sniffing is prohibited.

Forms, multipart, uploads, compression, and streaming formats remain deferred.

## 12. Runtime Record reservation

Before Handler execution, every admitted business request reserves:

```text
RecordId
queue capacity
record/event budget
durability policy
required storage health
```

Default policy is `required`. Failure to reserve or safely queue the record rejects the request before business handling.

`best_effort` is permitted only as an explicit policy and must expose incomplete/drop state and health metrics. LingShu never claims full auditability after loss.

## 13. Runtime Record event envelope

Every append-only event includes:

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

Event sequence increases within one Record. Attributes are allowlisted, bounded, and redacted. Header/query/body/cookie content is absent by default. Approved capture uses bounded summaries or external references.

## 14. Default local writer

Default storage uses rotated append-only UTF-8 JSON Lines segments:

```text
<record_base>/
  manifest.json
  active/
  closed/
  quarantine/
```

Rules:

- framework-generated safe filenames;
- canonical base-path containment;
- reject symlink traversal, path traversal, and unsafe ownership/permissions;
- one complete event per line;
- active segment append only;
- atomic manifest updates through temporary file and rename;
- closed segments become retention candidates;
- external storage backends remain extensions.

## 15. Durability declaration

```text
buffered
flush
fsync
```

The selected policy is visible in health and diagnostics and cannot claim stronger guarantees than it provides. Fsync frequency remains bounded and configurable.

## 16. Independent resource budgets

Limits exist for:

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
cleanup work/time per cycle
flush deadline
shutdown flush deadline
recovery work/time
```

All limits produce stable error codes and telemetry.

## 17. Disk watermarks

### Normal

Full configured capture within limits.

### Soft

Reduce optional detail, truncate approved summaries, accelerate cleanup, and emit warning health.

### Hard

Mark not-ready and reject new `required` business requests while preserving cleanup and minimal diagnostics.

### Critical reserve

Stop nonessential record writes and preserve only failure, health, shutdown, and data-loss diagnostics required to protect process/filesystem stability.

Active segments are never deleted by retention cleanup.

## 18. Retention and crash recovery

Retention deletes only closed, unreferenced segments satisfying age/policy and is bounded per cycle.

Startup recovery:

1. obtain writer lock/lease;
2. validate storage root and permissions;
3. load or rebuild manifest;
4. scan active tails;
5. truncate incomplete final lines;
6. validate required envelope fields and versions;
7. quarantine unrecoverable segments;
8. rebuild indexes and counters;
9. report recovery and estimated loss;
10. become ready only if the configured policy can be honored.

Recovery has a Deadline and work budget. Exceeding it leaves the service not-ready rather than hanging startup.

## 19. Common telemetry fields

Where applicable, logs, traces, diagnostic events, and Runtime Records use:

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

Non-applicable fields are omitted.

## 20. Redaction classes

```text
public
internal
sensitive
secret
```

- public: safe for configured outputs;
- internal: diagnostic only and not client-visible by default;
- sensitive: emitted only under explicit omit/hash/tokenize/truncate policy;
- secret: never emitted.

Authorization/Cookie headers, query/body values, credentials, tokens, configuration secrets, SQL parameters, and internal exception messages/paths are sensitive by default.

## 21. Metric-cardinality rules

Prohibited labels:

```text
request_id
record_id
trace_id
operation_id
connection_id
raw path
raw error message
user or tenant ID by default
```

Allowed bounded dimensions include component, route name/template, method, status class, outcome, stable error code, cancellation reason, and worker role.

## 22. Required acceptance matrix

Implementation must cover:

- identifier generation, format, type isolation, and inbound trust boundaries;
- stable error catalog, safe problem response, cause redaction, fatal scope, and cancellation preservation;
- deterministic configuration precedence, schema migration, secret redaction, immutable snapshots, reload, rollback, and degraded state;
- JSON encoding/decoding limits, duplicate keys, non-finite numbers, explicit custom types, and 406/415;
- Runtime Record reservation before Handler, saturation policies, rotation, retention, permissions, symlink/path traversal, disk watermarks, recovery, and shutdown flush;
- telemetry field consistency, redaction, and metric-cardinality enforcement;
- no secret leakage through any output path.

## 23. Deferred decisions

- exact numeric defaults and retention duration;
- configuration file syntax and secret-provider implementations;
- multi-Worker reload transport/consensus;
- forms, multipart, uploads, compression, and streaming serialization;
- concrete logger, metrics, tracing, database, and object-storage backends;
- official OpenTelemetry integration;
- cross-machine clock synchronization;
- post-v1.0 error-code compatibility guarantees.
