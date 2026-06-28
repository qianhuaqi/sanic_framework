# P0 Architecture Decision Status

- Status: Active P0 control document
- Parent Issue: #25
- Active decision Issue: none
- Last accepted decision: P0-D3 / ADR-003 / PR #38
- Last updated: 2026-06-28

## Authority

`LINGSHU_FRAMEWORK_BLUEPRINT.md` is the single overall architecture document. This file records decision state only.

- **Confirmed** decisions may be used by later implementation Issues.
- **Proposed** and **Candidate** decisions must not be implemented.
- **Rejected** decisions require a new Issue, ADR, and project-lead approval before reconsideration.

## Confirmed

### Project identity

- LingShu is a new, independently implemented Python Web/API framework.
- It is not based on Sanic, FastAPI, Flask, Django, Starlette, or another upper-level Web framework.
- The archived implementation creates no compatibility obligation.
- Production framework code will be written from scratch.

### P0-D1: Single repository and development concurrency

- Canonical repository: `qianhuaqi/lingshu`.
- ADR-001 accepted; Issue #31 completed; PR #32 merged.
- Concurrent work uses separate Issues, writer-prefixed branches, primary writers, worktrees or clones, virtual environments, and Pull Requests.
- Write scopes do not overlap.
- Shared contracts merge before dependent work.
- Development may be parallel; integration into `main` is serial.

### P0-D2: Runtime concurrency

- ADR-002 accepted; Issue #34 completed; PR #35 merged.
- Standard-library `asyncio` behavior is the correctness baseline.
- Each Worker owns one event loop and one Application Runtime.
- Runtime ownership is Supervisor → Worker → Application → Connection → Request → Operation.
- Request-created tasks are request-owned by default.
- Fire-and-forget tasks are prohibited.
- One HTTP/1.1 connection executes one request at a time.
- Admission, queues, buffers, executors, dependencies, telemetry, and records are bounded.
- Deadline is absolute and monotonic.
- Cancellation propagates to children.
- Blocking work is isolated from the event loop.
- Worker restart is bounded and crash loops stop.
- Shutdown drains, cancels, cleans up, flushes, and escalates to hard stop.

### P0-D3: Package, source layout, and component boundaries

- ADR-003 accepted.
- Issue #37 completed.
- PR #38 merged at `66c977f435c23fc9aaa35c4f085a7ca20a81879a`.
- Detailed model: `docs/architecture/PACKAGE_AND_COMPONENT_LAYOUT.md`.

Confirmed packaging and layout:

```text
Repository:      qianhuaqi/lingshu
Distribution:    lingshu
Import package:  lingshu
Packaging file:  pyproject.toml
Production code: lingshu/
src layout:      prohibited
```

Confirmed components:

- `lingshu.core`;
- `lingshu.runtime`;
- `lingshu.http`;
- `lingshu.server`;
- `lingshu.record`;
- `lingshu.extensions`;
- `lingshu.cli`;
- `lingshu.testing`.

Confirmed dependency rules:

```text
runtime     → core
http        → runtime + core
server      → http + runtime + core
record      → core + stable runtime contracts
extensions  → core + runtime (+ documented HTTP contracts when required)
cli         → public composition surface
testing     → public/test-support surfaces
```

Additional confirmed rules:

- one framework version and release cadence;
- no initial component distributions or component-level `pyproject.toml` files;
- no dependency cycles;
- production components do not depend on `testing`;
- `lingshu/__init__.py` is the controlled public facade;
- deep imports remain private unless explicitly documented;
- optional dependencies load only when activated;
- Runtime Record mechanisms ship by default, while heavy exporters remain optional;
- wheel and sdist acceptance uses a fresh environment and tests outside the checkout.

### Repository reset, compatibility, and P0 gate

- Legacy implementation remains historical reference only at `archive/legacy-sanic-20260628`.
- No Sanic adapter, migration layer, or legacy API forwarding package is required before v1.0.
- P0 permits architecture and governance work only.
- No production package, directory skeleton, runtime dependency, or implementation phase may start before P0 acceptance.
- Every accepted request has an internal Request ID and bounded, redacted, recoverable Runtime Record.

## Rejected

- LingShu as a Sanic template or adapter;
- migration of the old runtime into the new source tree;
- legacy compatibility shims without released consumers;
- archived tests as acceptance tests for the new framework;
- separate repositories for initial framework components;
- multiple developers sharing one writable directory or branch;
- parallel branches changing the same contract or write scope;
- long-lived shared `develop` branch or automatic merge;
- one thread per request;
- unbounded tasks, queues, executors, or waiters;
- global mutable request context;
- resetting timeout at every nested layer;
- concurrent HTTP/1.1 request execution on one connection in the initial runtime;
- infinite Worker restart loops;
- shutdown without draining and cleanup;
- requiring a third-party event loop for correctness;
- `src/lingshu/` layout;
- initial `packages/` monorepo layout;
- multiple initial distributions such as `lingshu-core` and `lingshu-server`;
- multiple component-level `pyproject.toml` files;
- independent component versions;
- production components importing `lingshu.testing`;
- treating every deep import as public API;
- relying only on editable installation or checkout-root tests as packaging evidence.

## Candidate — not executable

### Recommended next decision: P0-D4 Application Kernel and request pipeline

- Application creation, ownership, and composition root;
- application lifecycle and freeze boundary;
- route registration, compilation, and immutability;
- exact request execution stage order;
- middleware scopes and ordering;
- Request/Response ownership and mutability;
- exception mapping and response commit semantics;
- minimum public API and controlled root exports;
- extension participation in startup, shutdown, and request handling.

### Remaining hardening and runtime details

- identifier standards;
- exception semantics and sensitive-data behavior;
- configuration versioning, validation, reload, and rollback;
- serialization rules;
- Runtime Record storage budgets and disk policy;
- minimum Python version and platform matrix;
- build backend and authoritative version-source mechanism;
- listener distribution and HTTP/2/HTTP/3 semantics;
- exact public Scope, Deadline, limiter, and cancellation names;
- exact numeric runtime defaults.

### Official capabilities and extensions

- Auth, Tenant, Tenant-Auth bridge, RBAC;
- Data, SQL, database drivers, Redis, Cache;
- i18n, OpenAPI, Observability, Resilience;
- Scheduler, Storage, and WebSocket;
- optional extras and official integration catalog.

### Release and public governance

- P1 and v0.x mapping;
- first public package release point;
- v1.0 API freeze scope;
- License, contribution policy, vulnerability reporting, supported security versions, changelog policy, and code of conduct.

## Confirmation rule

A proposal or candidate becomes Confirmed only after:

1. a dedicated Issue;
2. a Blueprint amendment or accepted ADR;
3. explicit project-lead confirmation;
4. reviewed and merged Pull Request;
5. this register is synchronized.

P1 remains blocked until all P0 exit conditions are met.
