# Development Handoff

Updated at: 2026-06-28
Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Phase: P0-D2 - Runtime Concurrency, Task Ownership, and Graceful Shutdown
Parent Issue: #25
Active decision Issue: #34
Active decision branch: `human/dodo/phase-p0-d2-runtime-concurrency`
Baseline: latest accepted `main`
Status: proposed architecture ready for review

## Previous accepted decision

### P0-D1: Single repository and concurrency governance

- Issue #31 completed.
- PR #32 merged.
- ADR-001 accepted.

## P0-D2 proposal completed on this branch

- Added `ADR-002-runtime-concurrency-model.md` with Proposed status.
- Added `RUNTIME_CONCURRENCY_MODEL.md` with the detailed implementable model.
- Defined standard-library asyncio semantics as the correctness baseline.
- Defined one event loop and one application runtime per Worker process.
- Defined Supervisor, Worker, Application, Connection, Request, and Operation ownership Scopes.
- Prohibited unregistered fire-and-forget tasks.
- Defined request-owned and application-owned background tasks.
- Defined one active request per HTTP/1.1 connection, with concurrency across connections.
- Defined hierarchical bounded admission control and bounded waiters.
- Defined transport, body, route, executor, dependency, telemetry, and Runtime Record backpressure.
- Defined absolute monotonic Deadline propagation.
- Defined cancellation reason taxonomy and parent-to-child propagation.
- Defined bounded thread and process executor isolation.
- Defined Worker crash restart budget and crash-loop stop.
- Defined runtime and shutdown state machines.
- Defined observability fields and concurrency/leak test matrix.

## Proposal summary

```text
Supervisor
└─ Worker process
   └─ one event loop
      └─ Application Runtime
         ├─ application-owned tasks
         └─ Connection
            └─ Request
               └─ Operation children
```

All task, queue, connection, request, executor, telemetry, and record resources are bounded.

## Intentionally deferred

- minimum Python version;
- public Scope, Deadline, limiter, and cancellation API names;
- exact numeric defaults;
- listener socket distribution strategy;
- mandatory optional accelerator support;
- HTTP/2 and HTTP/3 multiplexing;
- distribution count and physical source layout.

## Verification

This branch changes architecture and governance documentation only. It adds no production source, package skeleton, runtime dependency, framework implementation, or publishing configuration.

Review must verify:

- no orphan-task path exists;
- no queue or waiter is implicitly unbounded;
- Deadline is absolute and monotonic;
- cancellation cannot be silently swallowed;
- shutdown is ordered and bounded;
- HTTP/1.1 same-connection requests are not executed concurrently;
- multi-Worker semantics do not depend on shared mutable Python state;
- all deferred choices remain explicitly unresolved.

## Next action

Review the P0-D2 proposal and merge only if the runtime concurrency semantics are accepted. Do not start production implementation or P1.
