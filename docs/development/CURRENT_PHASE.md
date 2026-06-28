# Current Phase

Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Current phase: P0-D2 - Runtime Concurrency, Task Ownership, and Graceful Shutdown
Phase type: non-implementation architecture and governance
Accepted baseline: latest accepted `main`
Active decision branch: `human/dodo/phase-p0-d2-runtime-concurrency`
Active decision Issue: #34
Parent architecture Issue: #25
Status: proposed architecture under project-lead review
Next phase allowed: no

## Foundational fact

LingShu is a completely new, independently implemented Python Web/API framework.

It does not depend on Sanic, FastAPI, Flask, Django, Starlette, or any other upper-level Web framework. The archived implementation creates no compatibility obligation.

The previous implementation is preserved at `archive/legacy-sanic-20260628` and is not an active source of truth.

## Completed decisions

### P0-D1: Single repository and concurrency governance

Implemented by PR #32 and ADR-001.

Confirmed:

- one canonical GitHub repository: `qianhuaqi/lingshu`;
- independent Issue, branch, primary writer, worktree or clone, virtual environment, and Pull Request per concurrent task;
- explicit write scopes and dependency order;
- parallel development with serial integration into `main`.

## Active decision proposal

### P0-D2: Runtime concurrency

The proposal defines:

- standard-library `asyncio` semantics as the correctness baseline;
- one event loop per Worker process;
- Supervisor-managed Workers with bounded restart policy;
- structured task ownership from Supervisor to Operation Scope;
- request-owned versus application-owned tasks;
- sequential request execution per HTTP/1.1 connection and concurrency across connections;
- hierarchical bounded admission control;
- transport, body, route, executor, dependency, telemetry, and Runtime Record backpressure;
- absolute monotonic Deadline propagation;
- explicit cancellation reasons and parent-to-child propagation;
- bounded thread and process executors for blocking work;
- RUNNING → DRAINING → STOPPING → STOPPED shutdown semantics;
- context isolation, observability, and concurrency test requirements.

Detailed proposal:

- `docs/decisions/ADR-002-runtime-concurrency-model.md`
- `docs/architecture/RUNTIME_CONCURRENCY_MODEL.md`

## Explicitly unresolved

P0-D2 does not decide:

- minimum Python version;
- public API class and method names;
- exact numeric capacity and timeout defaults;
- mandatory third-party event loop or parser;
- listener socket distribution strategy;
- HTTP/2 and HTTP/3 multiplexing;
- distribution count, `packages/`, `src/`, or physical source layout.

## Current objective

1. review ADR-002 and the detailed runtime model;
2. confirm or revise ownership, Worker, admission, Deadline, cancellation, blocking-work, and shutdown semantics;
3. ensure the decision remains independent from unresolved package and directory choices;
4. open a documentation-only Pull Request;
5. keep P1 blocked.

## Out of scope

- production framework implementation;
- source package or directory skeleton creation;
- runtime dependency introduction;
- package publication;
- starting P1.

## Exit conditions for P0-D2

1. ADR-002 and the runtime concurrency model are reviewed and merged;
2. task ownership and background-task semantics are explicit;
3. Worker and event-loop semantics are explicit;
4. admission, backpressure, Deadline, cancellation, and blocking-work rules are explicit;
5. graceful shutdown and crash-restart semantics are explicit;
6. observability and test matrices are explicit;
7. deferred decisions remain marked unresolved;
8. the project lead performs the final merge.

P0 continues after P0-D2. P1 remains blocked.
