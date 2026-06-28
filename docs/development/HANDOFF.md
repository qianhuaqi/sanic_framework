# Development Handoff

Updated at: 2026-06-28
Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Phase: P0 - Architecture Decision Review and Blueprint Consolidation
Parent Issue: #25
Active decision Issue: none
Active decision branch: none
Baseline: latest accepted `main`
Status: P0-D5 accepted; awaiting P0-D6

## Accepted decisions

- P0-D1: repository and concurrent-development governance through ADR-001 / PR #32.
- P0-D2: runtime concurrency through ADR-002 / PR #35.
- P0-D3: package and component layout through ADR-003 / PR #38.
- P0-D4: Application Kernel and request pipeline through ADR-004 / PR #41.
- P0-D5: Hardening Foundations through ADR-005 / PR #44.

P0-D5 merge commit:

```text
704146f103e2daafac7e489951497411821e9ba9
```

## Confirmed time and identifier model

```text
Wall clock: RFC3339 UTC for timestamps, retention, and cross-process correlation
Monotonic: Deadline, timeout, queue wait, scheduling, and duration
```

```text
RequestId     128-bit / 32 lowercase hex
ConnectionId  128-bit / 32 lowercase hex
TraceId       128-bit / 32 lowercase hex
OperationId   128-bit / 32 lowercase hex
WorkerId      128-bit / 32 lowercase hex
RecordId      128-bit / 32 lowercase hex
RevisionId    SHA-256 / 64 lowercase hex
```

Runtime identifiers are opaque, non-semantic, typed, and immutable. LingShu always generates the internal RequestId. Inbound request IDs remain untrusted external correlation only.

## Confirmed error model

Framework errors have stable dotted codes, safe messages, client visibility, retryability, severity, fatal scope, optional safe details, and a private cause chain.

Client-visible framework errors use `application/problem+json`. Traceback, raw exception text, absolute path, environment/configuration data, credentials, secrets, SQL, request bodies, and internal topology are hidden by default.

Cancellation remains control flow and cannot be swallowed as an ordinary application error.

## Confirmed configuration model

```text
built-in defaults
< configuration file
< environment variables
< CLI overrides
< explicit programmatic overrides
```

Configuration is schema-driven, versioned, and strict on unknown or duplicate normalized keys. Secrets use a dedicated redacted type/provider reference. Runtime receives an immutable typed Snapshot.

Reload transaction:

```text
load
→ normalize
→ validate
→ resolve secrets
→ prepare resources
→ compile/freeze Revision
→ atomic publish
→ drain old Revision
→ cleanup old resources
```

Pre-publication failure leaves the old Revision unchanged. Unsafe post-publication recovery produces explicit degraded/not-ready state rather than hidden partial configuration.

## Confirmed serialization model

Baseline representations:

```text
text/plain; charset=utf-8
application/octet-stream
application/json; charset=utf-8
application/problem+json; charset=utf-8
```

JSON is UTF-8, bounded, and strict. Duplicate keys, NaN, and Infinity are rejected. Unknown objects are not serialized automatically. Datetime, bytes, Decimal, and custom domain values require explicit serializers.

Unsupported request media type produces 415. No acceptable response representation produces 406. Content sniffing is prohibited.

## Confirmed Runtime Record model

Every admitted business request reserves a RecordId, queue capacity, record/event budget, durability policy, and storage health before Handler execution.

Default business policy is `required`: failure to reserve the audit path rejects the request before business handling.

Default local storage:

```text
versioned event envelope
→ bounded queue
→ append-only UTF-8 JSON Lines segments
→ atomic manifest/index
→ retention and crash recovery
```

Durability policies are `buffered`, `flush`, and `fsync`, with no overstatement of guarantees.

Disk states:

```text
normal
→ soft watermark: reduce optional detail and accelerate cleanup
→ hard watermark: not-ready and reject required requests
→ critical reserve: minimal failure/health/shutdown diagnostics only
```

Recovery validates storage, rebuilds manifests when needed, truncates incomplete tail lines, quarantines unrecoverable segments, reports estimated loss, and becomes ready only when configured guarantees can be honored.

## Confirmed telemetry model

Logs, traces, diagnostics, and Runtime Records share names for timestamp, component, event, severity, outcome, framework/revision/worker/request/trace/operation identifiers, route, HTTP result, error code, retryability, cancellation reason, and duration.

Redaction classes:

```text
public
internal
sensitive
secret
```

High-cardinality IDs, raw paths, raw exception messages, and user/tenant identifiers are prohibited as default metric labels.

## Hardening integration status

`docs/architecture/P0_HARDENING_CHECKLIST.md` is now a Verified integration mapping. It no longer acts as an independent design source. The Blueprint and accepted ADRs remain authoritative.

## Intentionally deferred

- exact numeric defaults, retention, rotation, and fsync frequency;
- configuration file syntax and secret providers;
- multi-Worker reload coordination;
- form, multipart, uploads, compression, and streaming formats;
- concrete logging, metrics, tracing, database, or object-storage backends;
- official OpenTelemetry integration;
- public server/CLI contract;
- Python/platform support and build backend;
- official capabilities and extensions;
- release and public governance policy.

## Next decision

P0-D6 should define:

- public startup/serve boundary;
- CLI command model and application discovery;
- production/development execution and reload boundary;
- Worker/process options, signals, and exit codes;
- minimum Python and supported platform matrix;
- build backend and version source;
- console entry point, package metadata, and CI matrix;
- packaging and startup acceptance tests.

## Verification

P0-D5 added architecture and governance documentation only. No production source, package skeleton, runtime dependency, implementation, or publishing configuration was created.

P1 remains blocked.
