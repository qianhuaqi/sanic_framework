# P0 Architecture Decision Status

- Status: Active P0 control document
- Parent Issue: #25
- Active decision Issue: #40
- Active proposal: P0-D4 / ADR-004
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
- It is not based on another upper-level Web framework.
- The archived implementation creates no compatibility obligation.
- Production framework code will be written from scratch.

### P0-D1: Repository and development concurrency

- Canonical repository: `qianhuaqi/lingshu`.
- One Issue, writer branch, primary writer, isolated worktree/environment, and Pull Request per concurrent task.
- Non-overlapping write scopes and provider-first integration.
- Parallel development with serial integration into `main`.

### P0-D2: Runtime concurrency

- Standard-library `asyncio` behavior is the correctness baseline.
- One event loop and Application Runtime per Worker.
- Structured Supervisor → Worker → Application → Connection → Request → Operation ownership.
- Request-owned child tasks and no unregistered fire-and-forget tasks.
- One active HTTP/1.1 request per connection.
- Bounded admission, queues, executors, telemetry, and Runtime Records.
- Absolute monotonic Deadline and cancellation propagation.
- Blocking work isolation, bounded Worker restart, and ordered graceful shutdown.

### P0-D3: Package and component layout

```text
Repository:      qianhuaqi/lingshu
Distribution:    lingshu
Import package:  lingshu
Packaging file:  pyproject.toml
Production code: lingshu/
src layout:      prohibited
```

Confirmed components and direction:

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
- no initial component distributions;
- no dependency cycles;
- production components do not depend on `testing`;
- controlled root public facade;
- lazy optional integrations;
- default Runtime Record mechanisms with optional heavy exporters;
- wheel and sdist isolated-install quality gate.

### Repository reset, compatibility, and P0 gate

- Legacy implementation is historical reference only.
- No Sanic adapter, migration layer, or legacy API forwarding package is required before v1.0.
- P0 permits architecture and governance only.
- No production package, source tree, runtime dependency, or implementation phase begins before P0 acceptance.
- Every accepted request has an internal Request ID and bounded, redacted, recoverable Runtime Record.

## Proposed — P0-D4, not executable until merged

Issue #40 and ADR-004 propose:

- public `LingShu` composition root with a private low-level Application Kernel;
- Application lifecycle `CREATED → CONFIGURING → FROZEN → STARTING → RUNNING → DRAINING → STOPPING → STOPPED`;
- registration only before freeze;
- immutable Application Revision and atomic compiled-plan publication;
- failed freeze publishes no partial plan;
- immutable compiled routing and deterministic route conflict validation;
- asynchronous handler contract with one explicit Request argument;
- deterministic application and route Middleware onion ordering;
- single-use Scope-bound `call_next`;
- fixed request pipeline from Server acceptance through Request Scope cleanup;
- immutable Request metadata, scoped mutable state, and bounded single-consumer body;
- one-time return normalization;
- `None`, tuple response magic, arbitrary iterator, and unknown return values rejected by default;
- Response states `NEW → PREPARED → COMMITTED → COMPLETED/ABORTED`;
- no status/header mutation or replacement response after commit;
- deterministic route/application/HTTPException/default exception resolution;
- Extension contributions compiled before startup and immutable during request handling;
- minimum root exports `LingShu`, `Request`, `Response`, and `HTTPException`;
- contract tests for state, order, ownership, commit, error, extension, and import-side-effect behavior.

Proposal documents:

- `docs/decisions/ADR-004-application-kernel-request-pipeline-and-public-api.md`
- `docs/architecture/APPLICATION_KERNEL_AND_REQUEST_PIPELINE.md`

Until the decision PR is merged, these semantics remain Proposed and production implementation is prohibited.

## Rejected

- upper-level Web framework dependency;
- legacy runtime migration or compatibility shims without released consumers;
- separate initial repositories or distributions for framework components;
- shared writable development directory or multi-writer branch;
- automatic merge or long-lived shared `develop` branch;
- unbounded runtime resources, fire-and-forget tasks, or global mutable request state;
- one thread per request;
- resetting timeout at every nested layer;
- concurrent HTTP/1.1 requests on one connection in the initial runtime;
- infinite Worker restart loops;
- shutdown without drain and cleanup;
- requiring a third-party event loop for correctness;
- `src/lingshu/` or initial `packages/` layout;
- component-specific versions and packaging files;
- production dependency on `lingshu.testing`;
- treating all deep imports as public API;
- editable-install-only packaging evidence;
- running route or Middleware mutation;
- import-time registration;
- route conflict resolution by registration order;
- unordered Middleware;
- multiple `call_next` invocations;
- implicit sync handler execution on the event loop;
- implicit tuple or `None` response magic;
- mutable Request metadata;
- multiple Response commits or replacement after commit;
- per-request mutation of the compiled Application Plan.

## Candidate — not executable

### Deferred by P0-D4

- configuration reload and multi-Worker revision rollout;
- complete exception taxonomy and client error schema;
- Request/Connection/Trace/Operation identifier formats;
- JSON and other serialization rules;
- cookie, form, multipart, upload, and content-negotiation APIs;
- automatic `HEAD` and `OPTIONS`;
- host routing, reverse routing, mounting, and sub-applications;
- public server `run`/`serve` and CLI semantics;
- synchronous handler adaptation;
- dependency injection;
- exact numeric limits, timeouts, and media types.

### Official capabilities and protocols

- Auth, Tenant, Tenant-Auth bridge, RBAC;
- Data, SQL, database drivers, Redis, and Cache;
- i18n, OpenAPI, Observability, and Resilience;
- Scheduler, Storage, and WebSocket;
- HTTP/2 and HTTP/3;
- optional event-loop or parser accelerators.

### Support, packaging implementation, and governance

- minimum Python version and platform matrix;
- build backend and authoritative version-source mechanism;
- optional extras and official integration catalog;
- P1/v0.x mapping and first public release;
- v1.0 API freeze scope;
- License, contribution policy, vulnerability reporting, security-support versions, changelog policy, and code of conduct.

## Confirmation rule

A proposal or candidate becomes Confirmed only after:

1. a dedicated Issue;
2. a Blueprint amendment or accepted ADR;
3. explicit project-lead confirmation;
4. reviewed and merged Pull Request;
5. this register is synchronized.

P1 remains blocked until all P0 exit conditions are met.
