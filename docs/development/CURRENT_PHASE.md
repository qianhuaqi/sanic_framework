# Current Phase

Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Current phase: P0 - Architecture Decision Review and Blueprint Consolidation
Phase type: non-implementation architecture and governance
Accepted baseline: latest accepted `main`
Active decision branch: none
Active decision Issue: none
Parent architecture Issue: #25
Status: P0-D3 accepted; awaiting next architecture decision
Next phase allowed: no

## Foundational fact

LingShu is a completely new, independently implemented Python Web/API framework.

It does not depend on Sanic, FastAPI, Flask, Django, Starlette, or another upper-level Web framework. The archived implementation creates no compatibility obligation.

## Completed decisions

### P0-D1: Single repository and development concurrency

Accepted through ADR-001 and PR #32.

Confirmed:

- one canonical repository;
- isolated Issues, branches, worktrees, environments, and Pull Requests;
- declared write scopes and dependency order;
- parallel development with serial integration into `main`.

### P0-D2: Runtime concurrency

Accepted through ADR-002 and PR #35.

Confirmed:

- standard-library `asyncio` semantics as the correctness baseline;
- one event loop and Application Runtime per Worker;
- structured task ownership;
- bounded admission, queues, executors, telemetry, and records;
- absolute monotonic Deadline and cancellation propagation;
- event-loop isolation for blocking work;
- bounded Worker restart and ordered graceful shutdown.

### P0-D3: Package, source layout, and component boundaries

Accepted through ADR-003 and PR #38 at merge commit `66c977f435c23fc9aaa35c4f085a7ca20a81879a`.

Confirmed:

- one Python distribution: `lingshu`;
- one import package: `lingshu`;
- one root-level `pyproject.toml`;
- no `src/` layout;
- no initial `packages/` monorepo layout;
- production source directly under root-level `lingshu/`;
- internal components: `core`, `runtime`, `http`, `server`, `record`, `extensions`, `cli`, and `testing`;
- one framework version and release cadence;
- Runtime Record mechanisms included by default, with heavy exporters optional;
- explicit acyclic dependency direction;
- controlled root public facade;
- mandatory wheel/sdist clean-install verification outside the checkout.

## Still unresolved

- Application Kernel state model and composition root;
- request execution pipeline and exact stage ordering;
- Request, Response, Router, Middleware, and exception contracts;
- minimum public API and import surface;
- identifiers, exceptions, configuration, serialization, and Runtime Record storage budgets;
- built-in versus optional official capabilities;
- Python and platform support range;
- build backend and authoritative version-source mechanism;
- listener distribution and HTTP/2/HTTP/3 semantics;
- release, compatibility, license, contribution, and security policies.

## Recommended next decision

P0-D4 should decide Application Kernel, request execution pipeline, and minimum public API:

1. Application creation and composition responsibilities;
2. application lifecycle and immutable/frozen configuration boundary;
3. route registration and compile/freeze boundary;
4. exact request execution stage order;
5. middleware scopes and ordering;
6. Request/Response ownership and mutability rules;
7. exception mapping and response commit semantics;
8. minimal user-facing API and controlled root exports;
9. framework/application boundary and extension participation.

## Out of scope

- creating the production `lingshu/` tree or `pyproject.toml`;
- implementing Kernel, HTTP, Server, Router, Middleware, Record, CLI, or extensions;
- runtime dependency introduction;
- package publication;
- starting P1.

P1 remains blocked until all P0 exit conditions are satisfied and the project lead explicitly authorizes it.
