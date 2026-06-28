# Development Handoff

Updated at: 2026-06-28
Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Phase: P0 - Architecture Decision Review and Blueprint Consolidation
Parent Issue: #25
Active decision Issue: none
Active decision branch: none
Baseline: latest accepted `main`
Status: P0-D2 accepted; awaiting P0-D3 decision

## Accepted decisions

### P0-D1: Single repository and development concurrency

- Issue #31 completed.
- ADR-001 accepted.
- PR #32 merged.

### P0-D2: Runtime concurrency

- Issue #34 completed.
- ADR-002 accepted.
- PR #35 merged.
- Merge commit: `6809a18b0284d18fd1ee46d9af7183521a66d67c`.
- Detailed model: `docs/architecture/RUNTIME_CONCURRENCY_MODEL.md`.

Confirmed runtime model:

```text
Supervisor
└─ Worker process
   └─ one event loop
      └─ Application Runtime
         ├─ infrastructure tasks
         ├─ application-owned background tasks
         └─ Connection
            └─ Request
               └─ Operation children
```

Additional confirmed rules:

- standard-library `asyncio` semantics are the correctness baseline;
- Workers do not share mutable Python application state;
- request-created tasks are request-owned by default;
- unregistered fire-and-forget tasks are prohibited;
- one HTTP/1.1 connection executes one request at a time;
- concurrency, waiters, queues, buffers, executors, telemetry, and records are bounded;
- backpressure propagates through the full processing chain;
- Deadline is an absolute monotonic budget and is never reset by nested calls;
- cancellation has explicit reasons and propagates to children;
- blocking I/O and CPU-heavy work are isolated from the event loop;
- Worker restart is bounded and crash loops stop;
- graceful shutdown drains, cancels, cleans up, flushes, and escalates to hard stop;
- Context and Runtime Record data are Scope-local;
- leak, race, deadlock, slow-client, saturation, cancellation, and shutdown tests are mandatory.

## Intentionally deferred

- minimum Python version;
- public names for Scope, Deadline, limiter, and cancellation APIs;
- exact numeric capacity and timeout defaults;
- mandatory third-party event loop or parser;
- listener socket distribution strategy;
- HTTP/2 and HTTP/3 multiplexing;
- distribution count and physical source layout.

## Next decision

P0-D3 should decide:

- one distribution versus multiple distributions;
- direct `lingshu/` versus `src/lingshu/`;
- one versus multiple `pyproject.toml` files;
- physical boundaries for Core, HTTP, Server, Record, CLI, Testing, and Extensions;
- public import surface and dependency direction;
- placement of tests, examples, tools, benchmarks, protocol tests, and fuzzing assets.

## Verification

P0-D2 introduced architecture and governance documentation only. No production source, package skeleton, runtime dependency, implementation, or publishing configuration was added.

P1 remains blocked.
