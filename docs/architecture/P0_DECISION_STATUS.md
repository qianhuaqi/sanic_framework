# P0 Architecture Decision Status

- Status: Active P0 control document
- Parent Issue: #25
- Active decision Issue: none
- Last accepted decision: P0-D1 / ADR-001 / PR #32
- Purpose: track confirmation state without creating a second architecture design
- Last updated: 2026-06-28

## How to use this document

`LINGSHU_FRAMEWORK_BLUEPRINT.md` remains the single architecture design document. This file does not replace it. It records whether a Blueprint proposal is confirmed, rejected, or still unresolved.

Only **Confirmed** decisions may authorize a P1 implementation Issue. **Candidate** decisions must not be implemented. **Rejected** decisions must not be reintroduced without a new Issue, ADR, and project-lead approval.

## Confirmed decisions

### Project identity

- LingShu is a new, independently implemented Python Web/API framework.
- LingShu is not built on Sanic, FastAPI, Flask, Django, Starlette, or another upper-level Web framework.
- LingShu does not inherit a compatibility obligation from the archived repository.
- Production framework code will be written from scratch.

### Framework ownership

LingShu will define and control its own:

- application kernel;
- HTTP runtime;
- native server behavior;
- request and response model;
- routing and middleware mechanisms;
- lifecycle, cancellation, cleanup, and resource ownership;
- extension protocol;
- CLI and framework ecosystem.

These confirmed responsibilities do not yet confirm their directory or package placement.

### Single canonical repository

- The canonical repository is `qianhuaqi/lingshu`.
- Framework core, official capabilities, tests, documentation, examples, build tooling, protocol tests, security tests, and release metadata are governed in this repository unless a future accepted ADR proves a separate repository is necessary.
- This confirms one repository only. It does not yet confirm one distribution, multiple distributions, a `packages/` root, or a `src/` layout.
- ADR-001 defines the repository and concurrent-development model.
- Decision Issue #31 is completed.
- PR #32 merged the decision into `main` at commit `92d6c0795fd5a6d21841a8ac3a1896d703809e40`.

### Concurrent development governance

- Every concurrent task uses one Issue, one writer-prefixed branch, one primary writer, one independent worktree or clone, one independent virtual environment, and one Pull Request.
- Parallel tasks must declare non-overlapping write scopes.
- Overlapping write scopes, duplicate contract definitions, and shared cross-cutting files are serialized unless the project lead explicitly approves an exception.
- Development may be parallel, but integration into `main` is serial.
- Shared contracts and foundations merge before dependent features.
- Runtime concurrency is a separate architecture decision, but it must be bounded, isolated, cancellable, observable, and deterministically cleaned up.

### Repository reset

- The previous implementation is preserved at `archive/legacy-sanic-20260628`.
- Archive commit: `b869270e0ec7cbc324d17ef246e39d0873aab14f`.
- PR #28 established the greenfield active tree.
- Archived code, tests, dependencies, scaffolds, Issues, and Pull Requests are historical reference only.

### Compatibility policy

- No legacy API forwarding or compatibility package is required before v1.0.
- No Sanic adapter or migration layer is part of the new framework plan.
- A post-v1.0 compatibility policy must be approved before the first stable release.

### P0 implementation gate

- P0 is documentation, architecture, and governance only.
- No production package, directory skeleton, runtime dependency, or implementation phase may start before P0 acceptance.
- The project lead holds final architecture and merge authority.

### Request-level auditability

Issue #25 confirms that every accepted business request will have an internal request identifier and an independently managed runtime record, subject to redaction, bounds, retention, capacity, failure, and security rules.

The exact package placement and storage implementation remain unresolved.

## Rejected decisions

The following are rejected for the greenfield framework:

- LingShu as a Sanic template;
- Sanic as a LingShu core dependency;
- Sanic as an official required extension;
- a permanent Sanic adapter as the framework foundation;
- migration of the old runtime into the new source tree;
- old API compatibility shims without real released consumers;
- using archived tests as acceptance tests for the new framework;
- continuing the old C0/C1/C2 or R1-R6 implementation roadmap;
- separate repositories for Core, HTTP, Server, Record, or official capabilities during initial development;
- multiple developers writing in the same working directory;
- multiple primary writers on one branch;
- parallel branches modifying the same public contract or overlapping write scope;
- a long-lived shared `develop` branch;
- automatic merging of concurrent Pull Requests.

## Candidate decisions — not executable

The following Blueprint proposals are candidates only and must not be used to create P1 files or packages:

### Packaging inside the confirmed single repository

- one Python distribution versus multiple distributions;
- a `packages/` repository root;
- separate `lingshu-core`, `lingshu-http`, `lingshu-server`, `lingshu-record`, and `lingshu-cli` distributions;
- a thin aggregate distribution;
- one `pyproject.toml` versus multiple package-level `pyproject.toml` files;
- exact distribution names and import-package names.

### Source layout

- use of `src/<import_package>/`;
- direct root-level `lingshu/` package;
- exact Core, HTTP, Server, Record, CLI, testing, resource, and extension directories;
- top-level `examples/`, `scripts/`, `tools/`, `templates/`, benchmark, fuzz, protocol-test, and contract-test placement.

### Component boundaries

- whether Core, HTTP, Server, and Record are separate distributions or internal modules;
- exact dependency direction between those components;
- whether Request Record is built into the default installation or installed separately;
- whether WebSocket belongs to the server/runtime or a later optional package;
- exact extension lifecycle and capability-container design.

### Runtime concurrency implementation

The following remain unresolved even though the safety invariants are confirmed:

- event-loop implementation and supported alternatives;
- structured task-group API;
- worker and process model;
- thread and blocking-work isolation;
- per-app, per-worker, per-request, and per-operation concurrency ownership;
- concurrency limits and admission control;
- cancellation and deadline API;
- graceful shutdown and task-draining sequence;
- overload, race, deadlock, and resource-leak test matrix.

### Official extensions

The following are capability candidates, not approved package boundaries:

- Auth;
- Tenant;
- Tenant-Auth bridge;
- RBAC;
- Data and SQL;
- MySQL, PostgreSQL, MongoDB, and Redis integrations;
- Cache;
- i18n;
- OpenAPI;
- Observability;
- Resilience;
- Scheduler and storage integrations.

### Release and support policy

- exact P1 through P17 phase mapping;
- v0.x version mapping;
- supported Python version range;
- Linux and Windows support matrix;
- performance and accelerated-parser milestones;
- first public package release point;
- v1.0 API freeze scope.

## Pending consolidation

The requirements in `P0_HARDENING_CHECKLIST.md` are not a second architecture. Each accepted requirement must be incorporated into the Blueprint before P0 acceptance, including:

- monotonic versus system time;
- identifier standards;
- exception semantics;
- configuration versioning and reload;
- serialization rules;
- async context isolation;
- telemetry fields;
- worker and storage budgets.

After integration, the checklist must be archived or replaced with a verification record so it cannot drift from the Blueprint.

## Repository governance decisions still required

Before public release, the project lead must confirm:

- open-source license;
- contribution policy;
- vulnerability-reporting channel;
- supported security versions;
- changelog and release-note policy;
- code of conduct, if adopted.

These decisions do not block P0 architecture discussion but must be tracked before accepting external contributions or publishing packages.

## P0 exit rule

A candidate becomes confirmed only when all of the following exist:

1. a clear decision in Issue #25 or a dedicated Issue;
2. a Blueprint amendment or accepted ADR;
3. project-lead confirmation;
4. a reviewed and merged Pull Request;
5. this status register updated to match.

Until then, the decision remains non-executable.
