# P0 Architecture Decision Status

- Status: Active P0 control document
- Issue: #25
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
- continuing the old C0/C1/C2 or R1-R6 implementation roadmap.

## Candidate decisions — not executable

The following Blueprint proposals are candidates only and must not be used to create P1 files or packages:

### Repository and packaging

- monorepo with many independent distributions;
- a `packages/` repository root;
- separate `lingshu-core`, `lingshu-http`, `lingshu-server`, `lingshu-record`, and `lingshu-cli` distributions;
- a thin `lingshu-framework` aggregate distribution;
- one `pyproject.toml` per internal package;
- exact distribution names and import-package names.

### Source layout

- use of `src/<import_package>/`;
- direct root-level `lingshu/` package;
- exact Core, HTTP, Server, Record, CLI, testing, resource, and extension directories;
- top-level `examples/`, `scripts/`, `tools/`, `templates/`, benchmark, fuzz, protocol-test, and contract-test placement.

### Component boundaries

- whether Core, HTTP, Server, and Record are separate packages or internal modules;
- exact dependency direction between those components;
- whether Request Record is built into the default installation or installed separately;
- whether WebSocket belongs to the server/runtime or a later optional package;
- exact extension lifecycle and capability-container design.

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
