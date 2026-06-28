# P0 Architecture Decision Status

- Status: Active P0 control document
- Parent Issue: #25
- Active decision Issue: none
- Last accepted decision: P0-D5 / ADR-005 / PR #44
- Last updated: 2026-06-28

## Authority

`LINGSHU_FRAMEWORK_BLUEPRINT.md` is the single overall architecture document. This file records decision state only.

- **Confirmed** decisions may be used by later implementation Issues.
- **Proposed** and **Candidate** decisions must not be implemented.
- **Rejected** decisions require a new Issue, ADR, and project-lead approval before reconsideration.

## Confirmed decisions

### P0-D1

Single repository and concurrent-development governance are accepted through ADR-001 / PR #32.

### P0-D2

Runtime concurrency is accepted through ADR-002 / PR #35:

- standard-library `asyncio` correctness baseline;
- one event loop and Application Runtime per Worker;
- structured task ownership;
- bounded resources and backpressure;
- absolute monotonic Deadline and cancellation propagation;
- bounded Worker restart and graceful shutdown.

### P0-D3

Package and component layout are accepted through ADR-003 / PR #38:

```text
Repository:      qianhuaqi/lingshu
Distribution:    lingshu
Import package:  lingshu
Packaging file:  pyproject.toml
Production code: lingshu/
src layout:      prohibited
```

One version, one release cadence, controlled root facade, no initial component distributions, and machine-enforced dependency boundaries are confirmed.

### P0-D4

Application Kernel and request pipeline are accepted through ADR-004 / PR #41:

- public `LingShu` composition root and private Kernel;
- immutable Application Revision and atomic freeze;
- deterministic Router and Middleware;
- asynchronous Handler with explicit Request;
- fixed request pipeline;
- immutable Request metadata and bounded body;
- exactly-once response normalization;
- irreversible Response commit boundary;
- deterministic exception mapping;
- root exports `LingShu`, `Request`, `Response`, and `HTTPException`.

### P0-D5

Hardening Foundations are accepted through ADR-005 / PR #44 at merge commit `704146f103e2daafac7e489951497411821e9ba9`.

Confirmed:

- separate wall-clock and monotonic time semantics;
- typed opaque runtime identifiers and SHA-256 Revision identifiers;
- internal RequestId cannot be replaced by inbound correlation;
- stable dotted error codes and safe problem responses;
- deterministic configuration precedence, schema versions, protected values, immutable snapshots, reload, and rollback;
- strict bounded UTF-8 JSON and explicit content negotiation;
- Runtime Record reservation before business handling;
- versioned append-only event envelopes and JSON Lines segments;
- declared durability, bounded storage, disk watermarks, retention, and crash recovery;
- common telemetry fields, shared redaction rules, and bounded metric dimensions;
- the former Hardening Checklist is now a Verified integration mapping only.

Detailed model:

- `docs/decisions/ADR-005-hardening-foundations.md`
- `docs/architecture/HARDENING_FOUNDATIONS.md`
- `docs/architecture/P0_HARDENING_CHECKLIST.md`

## Rejected principles

- dependence on another upper-level Web framework;
- legacy runtime migration as the new implementation;
- `src/lingshu/` or initial multi-distribution packaging;
- shared writable development directories or automatic merge;
- unbounded tasks, queues, records, or disk;
- global mutable request state;
- timeout reset at nested layers;
- concurrent HTTP/1.1 requests on one connection;
- import-time registration or running-plan mutation;
- unordered Middleware or multiple `call_next` calls;
- implicit tuple/None response conventions;
- multiple Response commits;
- trusting inbound request identifiers as internal identifiers;
- exposing raw internal failures to clients;
- mutable partial configuration reload;
- permissive or arbitrary-object JSON encoding;
- reporting complete audit after record loss;
- high-cardinality identifiers as metric labels;
- wall-clock time for Deadline measurement.

## Candidate — not executable

### Recommended next decision: P0-D6

P0-D6 should define the executable and packaging baseline:

- public startup and serve API;
- CLI commands and application discovery;
- production/development execution and reload boundary;
- Worker/process options, signals, readiness, and exit codes;
- minimum Python and supported-platform matrix;
- build backend and authoritative version source;
- package metadata, console entry point, wheel/sdist, and CI matrix;
- startup, discovery, signal, packaging, and clean-install tests.

### Later decisions

- numeric defaults and environment profiles;
- advanced routing and body formats;
- sync Handler adaptation and dependency injection;
- official capabilities and extensions;
- HTTP/2, HTTP/3, and optional accelerators;
- release, compatibility, contribution, security, changelog, and code-of-conduct policy;
- final P0 freeze and P1 authorization.

## Confirmation rule

A proposal becomes Confirmed only after:

1. a dedicated Issue;
2. Blueprint amendment or accepted ADR;
3. explicit project-lead confirmation;
4. reviewed and merged Pull Request;
5. this register is synchronized.

P1 remains blocked until all P0 exit conditions are met.
