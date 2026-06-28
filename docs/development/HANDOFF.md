# Development Handoff

Updated at: 2026-06-28
Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Phase: P0-D5 - Hardening Foundations
Parent Issue: #25
Active decision Issue: #43
Active decision branch: `human/dodo/phase-p0-d5-hardening-foundations`
Baseline: latest accepted `main`
Status: proposed architecture ready for review

## Accepted decisions

- P0-D1: repository and development concurrency through ADR-001 / PR #32.
- P0-D2: runtime concurrency through ADR-002 / PR #35.
- P0-D3: package and component layout through ADR-003 / PR #38.
- P0-D4: Application Kernel and request pipeline through ADR-004 / PR #41.

## P0-D5 proposal completed on this branch

- Added `ADR-005-hardening-foundations.md`.
- Added `HARDENING_FOUNDATIONS.md`.
- Defined wall-clock versus monotonic time semantics.
- Defined typed Request, Connection, Trace, Operation, Worker, Record, and Revision identifiers.
- Defined internal correlation trust boundaries and inbound `X-Request-ID` handling.
- Defined framework exception taxonomy and stable dotted error codes.
- Defined safe `application/problem+json` client errors and cause redaction.
- Defined configuration source precedence and merge rules.
- Defined schema versions, explicit migrations, secret handling, and immutable Configuration Snapshots.
- Defined revision-based reload, atomic publication, rollback, and degraded-state behavior.
- Defined serializer registration, strict UTF-8 JSON, explicit custom types, and 406/415 negotiation.
- Defined Runtime Record reservation before Handler execution.
- Defined versioned event envelopes, append-only JSON Lines segments, atomic manifests, durability levels, budgets, watermarks, retention, and crash recovery.
- Defined shared telemetry fields, redaction classes, and metric-cardinality restrictions.
- Converted the temporary Hardening Checklist into a proposed integration-verification record.
- Added no production source, package skeleton, runtime dependency, or publishing configuration.

## Identifier proposal

```text
RequestId     128-bit / 32 lowercase hex
ConnectionId  128-bit / 32 lowercase hex
TraceId       128-bit / 32 lowercase hex
OperationId   128-bit / 32 lowercase hex
WorkerId      128-bit / 32 lowercase hex
RecordId      128-bit / 32 lowercase hex
RevisionId    SHA-256 / 64 lowercase hex
```

Runtime IDs are opaque, non-semantic, cryptographically random values. Inbound Request IDs never replace internal Request IDs.

## Error proposal

Framework errors have:

```text
stable code
safe message
client visibility
retryable flag
HTTP status when applicable
severity
fatal scope
safe details
private cause
```

Client errors use `application/problem+json`. Raw traceback, paths, secrets, configuration values, request bodies, SQL, credentials, and internal topology are not exposed.

## Configuration proposal

```text
defaults
< file
< environment
< CLI
< programmatic override
```

Runtime configuration is an immutable typed Snapshot. Reload uses load → normalize → validate → resolve secrets → prepare → freeze → atomic publish → drain old → cleanup. Failure before publication leaves the old Revision untouched.

## Serialization proposal

- text defaults to UTF-8 `text/plain`;
- bytes use `application/octet-stream`;
- JSON uses UTF-8 `application/json`;
- framework errors use `application/problem+json`;
- duplicate JSON keys and NaN/Infinity are rejected;
- depth, bytes, items, strings, and numeric tokens are bounded;
- datetime, bytes, Decimal, and custom values require explicit serializers;
- unsupported request media type returns 415;
- unacceptable response representation returns 406.

## Runtime Record proposal

Every admitted business request reserves a Runtime Record before Handler execution.

Default local storage:

```text
versioned event envelope
→ bounded queue
→ append-only JSON Lines segment
→ atomic manifest/index
→ retention and recovery
```

Default business-request policy is `required`: when record capacity cannot be reserved, new business requests are rejected before handling.

Disk states:

```text
normal
→ soft watermark: reduce optional detail and accelerate cleanup
→ hard watermark: not ready and reject required requests
→ critical reserve: minimal failure/health/shutdown diagnostics only
```

## Telemetry proposal

Logs, traces, diagnostics, and records share names such as:

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

High-cardinality IDs, raw paths, users, tenants, and exception text are prohibited as metric labels.

## Intentionally deferred

- exact numeric limits and retention durations;
- configuration file syntax and secret providers;
- multi-Worker reload transport/consensus;
- forms, multipart, uploads, compression, and streaming formats;
- concrete logging, metrics, tracing, database, and object-storage backends;
- OpenTelemetry integration;
- Python/platform support and build backend;
- public run/serve and CLI behavior;
- official business capabilities;
- release and governance policy.

## Verification

Review must verify:

- internal IDs cannot be replaced by external input;
- error codes are stable and client output is safe;
- secrets cannot leak through any output path;
- configuration reload cannot be partially visible;
- JSON handling is strict and bounded;
- no request enters business handling without the required Runtime Record reservation;
- disk-full and recovery behavior is explicit;
- high-cardinality identifiers never become metric labels;
- P1 remains blocked.

## Next action

Review and merge the P0-D5 decision Pull Request only if these hardening contracts are accepted. Do not start production implementation.
