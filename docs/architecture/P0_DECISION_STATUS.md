# P0 Architecture Decision Status

- Status: Active P0 control document
- Parent Issue: #25
- Active decision Issue: #37
- Active proposal: P0-D3 / ADR-003
- Last accepted decision: P0-D2 / ADR-002 / PR #35
- Last updated: 2026-06-28

## Authority

`LINGSHU_FRAMEWORK_BLUEPRINT.md` is the single overall architecture document. This file records decision state only.

- **Confirmed** may be used by a later implementation Issue.
- **Proposed** and **Candidate** must not be implemented.
- **Rejected** must not be reintroduced without a new Issue, ADR, and project-lead approval.

## Confirmed

### Project identity

- LingShu is a new, independently implemented Python Web/API framework.
- It is not based on Sanic, FastAPI, Flask, Django, Starlette, or another upper-level Web framework.
- The archived implementation creates no compatibility obligation.
- Production framework code will be written from scratch.

### Single repository and development concurrency — P0-D1

- Canonical repository: `qianhuaqi/lingshu`.
- ADR-001 is accepted; Issue #31 is completed; PR #32 is merged.
- Concurrent tasks use separate Issues, branches, primary writers, worktrees or clones, environments, and Pull Requests.
- Write scopes must not overlap.
- Shared contracts merge before dependent work.
- Development may be parallel; integration into `main` is serial.

### Runtime concurrency — P0-D2

- ADR-002 is accepted; Issue #34 is completed; PR #35 is merged.
- Standard-library `asyncio` behavior is the correctness baseline.
- Each Worker owns one event loop and one Application Runtime.
- Runtime ownership is Supervisor → Worker → Application → Connection → Request → Operation.
- Request-created tasks are request-owned by default.
- Fire-and-forget tasks are prohibited.
- HTTP/1.1 executes one request at a time per connection.
- Admission, queues, buffers, executors, telemetry, and records are bounded.
- Deadline is absolute and monotonic.
- Cancellation propagates to children.
- Blocking work is isolated from the event loop.
- Worker restart is bounded and crash loops stop.
- Shutdown drains, cancels, cleans up, flushes, and escalates to hard stop.

### Repository reset, compatibility, and P0 gate

- Legacy implementation remains historical reference only at `archive/legacy-sanic-20260628`.
- No Sanic adapter, migration layer, or legacy API forwarding package is required before v1.0.
- P0 permits architecture and governance work only.
- No production package, directory skeleton, runtime dependency, or implementation phase may start before P0 acceptance.
- Every accepted request has an internal Request ID and bounded, redacted, recoverable Runtime Record.

## Proposed — P0-D3, not executable until merged

Issue #37 and ADR-003 propose:

- one initial Python distribution named `lingshu`;
- one import package named `lingshu`;
- one root-level `pyproject.toml`;
- no `src/` layout;
- no initial `packages/` monorepo layout;
- production source directly under root-level `lingshu/`;
- internal components `core`, `runtime`, `http`, `server`, `record`, `extensions`, `cli`, and `testing`;
- one framework version and release cadence for all internal components;
- Runtime Record mechanisms installed by default, while heavy exporters remain optional;
- explicit component responsibilities and acyclic dependency rules;
- a controlled root public facade with explicit exports;
- lazy optional dependencies that do not become hidden core requirements;
- root-level tests, docs, examples, tools, benchmarks, and fuzz directories;
- wheel and sdist build, clean virtual-environment installation, and tests from outside the checkout.

Project-lead direction already recorded:

- `src/` is not to be added.

Proposal documents:

- `docs/decisions/ADR-003-package-source-layout-and-component-boundaries.md`
- `docs/architecture/PACKAGE_AND_COMPONENT_LAYOUT.md`

Until the decision PR is merged, no production directory or packaging file may be created.

## Rejected

- LingShu as a Sanic template or adapter.
- Migration of the old runtime into the new source tree.
- Legacy compatibility shims without released consumers.
- Archived tests as acceptance tests for the new framework.
- Separate repositories for initial framework components.
- Multiple developers sharing one writable directory or branch.
- Parallel branches changing the same contract or write scope.
- Long-lived shared `develop` branch or automatic merge.
- One thread per request.
- Unbounded tasks, queues, executors, or waiters.
- Global mutable request context.
- Resetting timeout at every nested layer.
- Concurrent HTTP/1.1 request execution on one connection in the initial runtime.
- Infinite Worker restart loops.
- Shutdown without draining and cleanup.
- Requiring a third-party event loop for correctness.

## Candidate — not executable

### Deferred by P0-D3

- minimum supported Python version;
- build backend;
- exact public application, request, response, Scope, Deadline, limiter, and cancellation names;
- exact public API manifest mechanism;
- authoritative version-file mechanism;
- optional dependency extras and official integration catalog;
- first PyPI release timing;
- post-v1.0 compatibility policy.

### Component and extension details

- WebSocket, OpenAPI, and Observability placement;
- Auth, Tenant, RBAC, Data, SQL, database drivers, Redis, Cache, i18n, Resilience, Scheduler, and Storage boundaries;
- listener socket distribution strategy;
- HTTP/2 and HTTP/3 multiplexing.

### Release and public governance

- P1 and v0.x mapping;
- Python and platform support matrix;
- first public package release point;
- v1.0 API freeze scope;
- License, contribution policy, vulnerability reporting, supported security versions, changelog policy, and code of conduct.

## Pending hardening consolidation

P0-D2 integrated monotonic Deadline, Async Context isolation, bounded runtime resources, and part of the Telemetry requirements.

Before P0 acceptance, remaining hardening requirements must be integrated: identifier standards, exception semantics, configuration versioning and reload, serialization rules, Runtime Record storage budgets, and disk policy.

## Confirmation rule

A proposal or candidate becomes Confirmed only after:

1. a dedicated Issue;
2. a Blueprint amendment or accepted ADR;
3. explicit project-lead confirmation;
4. reviewed and merged Pull Request;
5. this register is synchronized.

P1 remains blocked until all P0 exit conditions are met.
