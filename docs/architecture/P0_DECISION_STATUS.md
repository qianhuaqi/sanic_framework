# P0 Architecture Decision Status

- Status: Frozen when PR #51 is merged
- Parent Issue: #25 (closed by PR #51)
- Final decision Issue: #49 (closed by PR #51)
- Final Freeze Pull Request: #51
- Authoritative P0 freeze commit: merge commit of PR #51
- Accepted decisions: ADR-001 through ADR-007
- Next phase: P1 - Single-Worker Minimum Vertical Slice
- First authorized implementation Issue: P1-00 after PR #51 merges
- Last updated: 2026-06-28

## Authority

`LINGSHU_FRAMEWORK_BLUEPRINT.md` is the single overall architecture document. Accepted ADRs contain detailed contracts. `P0_FINAL_FREEZE.md` records the final audit and authorization boundary.

After PR #51 merges:

- P0 decisions are Frozen;
- P1 may implement only the scope declared by `P1_IMPLEMENTATION_PLAN.md`;
- changing a frozen decision requires a dedicated Issue and a new ADR that explicitly amends or supersedes it;
- implementation cannot silently reinterpret P0.

## Accepted decisions

### P0-D1 / ADR-001: Repository and development concurrency

- canonical repository `qianhuaqi/lingshu`;
- one Issue, writer-prefixed branch, primary writer, isolated worktree/environment, and PR per task;
- explicit base commit, write scope, dependencies, conflicts, integration order, and checks;
- provider-first integration;
- parallel development with serial merge to `main`;
- no shared writable worktree, multi-writer branch, direct `main`, long-lived `develop`, or auto-merge;
- project lead retains final merge authority.

### P0-D2 / ADR-002: Runtime concurrency

- standard-library `asyncio` semantics are the correctness baseline;
- one event loop and Application Runtime per Worker;
- Supervisor → Worker → Application → Connection → Request → Operation ownership;
- request-owned child tasks and no unregistered fire-and-forget tasks;
- one active HTTP/1.1 request per connection;
- bounded admission, queues, buffers, executors, dependencies, telemetry, and records;
- absolute monotonic Deadline, cancellation propagation, blocking-work isolation;
- bounded Worker restart and ordered graceful shutdown.

### P0-D3 / ADR-003: Package and component layout

```text
Repository:      qianhuaqi/lingshu
Distribution:    lingshu
Import package:  lingshu
Production code: lingshu/
Packaging file:  pyproject.toml
src layout:      prohibited
```

- one distribution, version, and release cadence;
- controlled root facade;
- components `core`, `runtime`, `http`, `server`, `record`, `extensions`, `cli`, and `testing`;
- acyclic machine-checkable dependency direction;
- production code never depends on testing helpers;
- wheel/sdist verified through non-editable installation outside checkout.

### P0-D4 / ADR-004: Application Kernel and request pipeline

- public root facade: `LingShu`, `Request`, `Response`, `HTTPException`;
- private Kernel with immutable Application Revision and Plan;
- atomic freeze and immutable running registries;
- deterministic Router and Application/Route Middleware onion ordering;
- async Handler with one explicit Request;
- immutable Request metadata and bounded single-consumer body;
- exactly-once return normalization;
- irreversible Response commit boundary;
- deterministic exception resolution and extension lifecycle.

### P0-D5 / ADR-005: Hardening Foundations

- separate RFC3339 UTC wall time and process-local monotonic time;
- typed opaque runtime identifiers and SHA-256 RevisionId;
- internal RequestId cannot be replaced by inbound correlation;
- stable dotted error codes and safe problem responses;
- strict versioned configuration, protected values, immutable Snapshot, revision-based reload/rollback;
- bounded strict UTF-8 JSON and explicit content negotiation;
- Runtime Record reservation before Handler;
- append-only event envelopes, bounded queue/storage, disk watermarks, retention, and crash recovery;
- shared telemetry fields, redaction classes, and bounded metric cardinality;
- Hardening Integration Verification is Verified.

### P0-D6 / ADR-006: Executable, CLI, support, and build baseline

- Application, Server, Supervisor, and CLI ownership separated;
- documented public single-Worker `Server`, `ServerConfig`, and `serve`;
- CLI `run`, `check`, and `version`;
- strict `module:attribute` discovery and explicit synchronous zero-argument factory;
- multi-Worker design uses cross-platform spawn, one-time listener bind/transfer, RevisionId-consistent readiness, restart budgets, and stable exit codes;
- development reload is single-Worker process replacement and is distinct from production configuration reload;
- CPython >=3.12; required 3.12/3.13/3.14; visible 3.15 preview;
- Tier 1 64-bit Linux, Windows, and macOS;
- Hatchling, PEP 621, static `[project].version`, console script, pure wheel/sdist, and clean-install CI matrix.

### P0-D7 / ADR-007: Governance, compatibility, release, and final freeze

```text
License:        Apache-2.0
Contribution:   DCO 1.1 + Signed-off-by
CLA:            none initially
Conduct:        Contributor Covenant 2.1 adaptation
Versioning:     SemVer 2.0.0 with stricter 0.x rules
First P1:       0.1.0.dev0
Long-lived:     main only
Final Freeze:   PR #51
```

- private vulnerability reporting and supported-version policy;
- changelog categories `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`;
- pre-1.0 patch compatibility within a minor line;
- breaking pre-1.0 changes require a minor bump, migration guidance, and normally prior deprecation;
- post-1.0 breaking changes require a major release;
- normal post-1.0 removal requires two released minors and 180 days;
- tag-driven protected CI artifacts, immutable published versions, trusted short-lived publication credentials, hashes, and provenance/attestation;
- P1 limited to the single-Worker minimum vertical slice;
- PR #51 merge is the sole P0 completion and P1 authorization event.

## P1 authorized scope

After PR #51 merges, P1 may implement:

```text
P1-00 package/tooling/CI
P1-01 core primitives
P1-02 static configuration
P1-03 runtime Scope/Deadline/cancellation/admission
P1-04 HTTP model/body/response
P1-05 Router/Middleware
P1-06 Application Kernel/freeze/lifecycle
P1-07 minimum Runtime Record
P1-08 native single-Worker HTTP/1.1 Server
P1-09 CLI version/check/run --workers 1
P1-10 integration/security/packaging/docs
```

P1 Issues must follow provider-first dependencies and the exact scopes in `docs/development/P1_IMPLEMENTATION_PLAN.md`.

## Deferred beyond P1

- public PyPI production publication;
- multi-Worker Supervisor and listener-transfer implementation;
- development reload and production configuration rollout;
- automatic HEAD/OPTIONS, host/reverse routing, mounts, and sub-applications;
- advanced streaming, form, multipart, uploads, compression, and content encodings;
- sync Handler adaptation and dependency injection;
- official Auth, Tenant, RBAC, SQL, Redis, Cache, i18n, OpenAPI, Resilience, Scheduler, Storage, and Observability integrations;
- HTTP/2, HTTP/3, WebSocket, ASGI, and WSGI;
- PyPy, free-threaded, 32-bit, extra platforms, and native extensions;
- public release date, manual signature scheme, trademark, paid support, and LTS governance.

## Rejected principles

The frozen architecture rejects:

- dependence on another upper-level Web framework;
- legacy implementation as the new runtime;
- `src/lingshu/` or initial multiple distributions;
- shared writable workspaces, multi-writer branches, direct `main`, long-lived `develop`, and auto-merge;
- unbounded runtime resources, records, or disk;
- global mutable request state and import-time runtime side effects;
- timeout reset, swallowed cancellation, or unmanaged tasks;
- concurrent HTTP/1.1 request execution on one connection;
- running-plan mutation, route conflict resolution by registration order, repeated `call_next`, or implicit response magic;
- trusting inbound IDs as internal IDs or exposing raw internal failures;
- partial mutable configuration reload, arbitrary-object JSON, or audit claims after record loss;
- Application as process Supervisor, fork-only correctness, Worker bind races, or arbitrary target evaluation;
- duplicate version literals, workstation-built authoritative releases, mutable published artifacts, or long-lived package-index credentials;
- arbitrary breaking `0.x` patch releases;
- broad P1 implementation before the single-Worker vertical slice.

## Freeze rule

The project lead's merge of PR #51:

1. closes Issue #49 and #25;
2. establishes the PR #51 merge commit as the final P0 commit;
3. marks this status Frozen;
4. authorizes P1;
5. allows creation of P1-00 first;
6. leaves all governance and final-merge controls active.
