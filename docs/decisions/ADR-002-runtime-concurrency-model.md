# ADR-002: Runtime concurrency, task ownership, and graceful shutdown

- Status: Proposed
- Date: 2026-06-28
- Parent architecture Issue: #25
- Decision Issue: #34

## Context

LingShu must process many connections and requests concurrently without unbounded queues, request-context leakage, orphan tasks, blocked event loops, cancellation loss, or shutdown corruption.

The framework must work consistently on development machines and production systems while remaining independently implemented and not depending on another Web framework.

This decision defines runtime concurrency semantics. It does not define the final source directory, Python distribution layout, minimum Python version, HTTP/2 or HTTP/3 semantics, or a third-party event-loop dependency.

## Decision

### 1. Standard asynchronous baseline

Python standard-library `asyncio` semantics are the required baseline.

LingShu must run correctly without a third-party event loop. A future optional accelerator may be supported only through a separate ADR and must preserve the same observable semantics.

### 2. One event loop per Worker process

A Worker process owns exactly one event loop and one application runtime instance.

A Supervisor may manage one or more Workers. Workers do not share mutable Python application state. Cross-Worker coordination requires an explicit IPC, database, cache, message, or operating-system mechanism.

Single-Worker execution is the semantic reference. Multi-Worker execution is a scale-out layer and must not change request, cancellation, shutdown, or extension lifecycle semantics.

### 3. Structured ownership tree

Every runtime task belongs to an explicit ownership Scope:

```text
Supervisor
└─ Worker
   └─ Application Runtime
      ├─ Listener / Server tasks
      ├─ Application-owned background tasks
      └─ Connection
         └─ Request
            └─ Operation / child tasks
```

A child Scope cannot outlive its owner unless it is explicitly transferred to a longer-lived Scope through a reviewed framework API.

Unregistered fire-and-forget tasks are prohibited. Direct task creation that bypasses LingShu ownership tracking is not a supported framework operation.

### 4. Request-owned and application-owned tasks

A task created while handling a request is request-owned by default.

When the request completes, times out, disconnects, or is cancelled, remaining request-owned tasks are cancelled and awaited within a bounded cleanup budget.

Long-lived background work must be explicitly registered as application-owned or Worker-owned. Its registration must declare name, owner, start phase, stop policy, failure policy, restart policy, deadline, and shutdown behavior.

Request context must not leak into detached background tasks. Context inheritance is cleared or deliberately reconstructed when ownership transfers.

### 5. HTTP/1.1 connection concurrency

For the initial HTTP/1.1 runtime, one connection may execute at most one request at a time.

Multiple connections execute concurrently. Keep-alive requests on one connection are processed sequentially. LingShu does not concurrently execute pipelined HTTP/1.1 requests or emit out-of-order responses.

Read-ahead buffering is bounded. Protocol input arriving beyond configured limits is paused, rejected, or causes connection termination according to protocol and security policy.

HTTP/2 and HTTP/3 multiplexing require separate future decisions.

### 6. Hierarchical admission control

Concurrency is controlled at multiple levels:

- Supervisor and total Worker budget;
- Worker connection budget;
- Worker active-request budget;
- optional application and route budget;
- background-task budget;
- blocking-executor worker and queue budget;
- outbound dependency budget;
- Runtime Record and telemetry queue budget.

Waiting queues are bounded and have a maximum wait deadline. Reaching capacity produces backpressure or an explicit rejection. The framework must never create an unbounded waiter list merely because a semaphore is used internally.

### 7. Backpressure and slow clients

Transport reads and writes participate in backpressure.

- input reading pauses when parsing, body, request, or application capacity is exhausted;
- streaming request bodies expose bounded flow control;
- response streaming waits for transport drain signals;
- write buffers have high and low watermarks;
- header, body, idle, read-progress, write-progress, and total-request deadlines are distinct;
- slow clients cannot reserve unlimited Worker resources.

When a complete HTTP response can still be safely produced, overload may return an explicit service-unavailable response. Otherwise the connection is closed and the reason is recorded.

### 8. Absolute monotonic Deadline

Timeout budgeting uses an absolute monotonic Deadline.

A child operation receives the same Deadline or an earlier one. It never receives a fresh copy of the original duration. All route, middleware, extension, database, cache, outbound HTTP, streaming, and cleanup operations consume the remaining budget.

System wall-clock time is used for human-readable timestamps, not timeout measurement.

### 9. Cancellation reasons and propagation

Cancellation carries a framework reason, including at least:

- client disconnect;
- request deadline exceeded;
- server draining;
- Worker stopping;
- parent operation cancelled;
- explicit application cancellation;
- resource admission failure.

Cancellation propagates from owner to children. Code may perform bounded cleanup but must not silently swallow cancellation and continue normal request work.

Shielding is allowed only for narrow, bounded, explicitly documented cleanup or commit sections. Shielding cannot create an unbounded shutdown delay.

### 10. Blocking and CPU-intensive work

Blocking work must not execute directly on the Worker event loop.

Blocking I/O uses a bounded thread executor. CPU-intensive work uses a bounded process executor or an external job system when configured.

Executor worker counts and submission queues are bounded. Queue admission has a timeout. Cancellation of already-running thread work is best-effort; the request result is discarded if ownership is cancelled, and the outstanding work remains accounted for until completion.

The framework must expose overload and orphan-risk telemetry for executor work.

### 11. Supervisor and Worker lifecycle

The Supervisor owns Worker processes, readiness aggregation, signal handling, restart policy, and final exit status.

Worker startup must complete initialization before readiness is announced. Startup failure triggers reverse-order cleanup.

Unexpected Worker exit may trigger a bounded restart policy with rate limit and backoff. A crash loop must stop automatic restarts and mark the service unhealthy rather than restart forever.

The cross-platform semantic baseline must not depend on fork-only inherited mutable state. Platform-specific optimizations may be added later if they preserve lifecycle semantics.

### 12. Graceful shutdown state machine

The runtime state sequence is:

```text
STARTING → RUNNING → DRAINING → STOPPING → STOPPED
```

Shutdown proceeds in order:

1. mark the service not ready;
2. stop accepting new connections;
3. stop admitting new requests and background work;
4. drain active requests and response streams until the graceful Deadline;
5. cancel remaining request and operation Scopes;
6. stop application-owned background tasks according to policy;
7. close extensions and external resources in reverse startup order;
8. flush Runtime Record and telemetry within bounded budgets;
9. close listeners, transports, and executors;
10. exit Workers and aggregate Supervisor status;
11. after the hard-stop Deadline, terminate remaining processes and record forced shutdown.

Shutdown calls are idempotent. A second signal may shorten the remaining grace period but must not skip required best-effort cleanup reporting.

### 13. Context isolation

Request, connection, operation, deadline, cancellation reason, identity, and Runtime Record context are Scope-local.

Context-local mechanisms may be used internally, but object ownership remains explicit. Application singletons must not retain request-scoped objects after Scope completion.

Detached application tasks start with a clean request context unless an explicit safe value is copied.

### 14. Runtime Record and telemetry under concurrency

Every request records its Scope, Deadline, cancellation reason, admission decisions, queue waits, executor submissions, child-task outcomes, and final cleanup result.

Record and telemetry pipelines are bounded. Their overload policy must be explicit: truncate noncritical detail, aggregate, reject new work in strict-audit mode, or fail according to configuration. Silent unbounded buffering is prohibited.

### 15. Required observability

The runtime exposes at least:

- active and accepted connections;
- active, queued, completed, rejected, timed-out, disconnected, and cancelled requests;
- task counts by owner Scope;
- background-task failures and restarts;
- admission wait time and rejection reason;
- read and write backpressure duration;
- executor active work, queue depth, timeout, and abandoned-result count;
- Worker start, ready, drain, crash, restart, and forced-stop counts;
- shutdown remaining tasks and cleanup failures;
- Runtime Record queue depth, drops, truncations, and failures.

### 16. Required test matrix

Implementation acceptance must include deterministic tests for:

- many concurrent short connections and requests;
- keep-alive sequential request handling;
- attempted HTTP/1.1 pipelining;
- slow headers, slow body, slow response reader, and stalled streaming;
- client disconnect before, during, and after handler execution;
- route and global capacity saturation;
- bounded waiter and executor queue saturation;
- parent-to-child cancellation propagation;
- Deadline budget not being reset by nested calls;
- cancellation during extension, database, cache, and outbound-call cleanup;
- request-context isolation across concurrent requests;
- detached background task context clearing;
- Worker startup failure and rollback;
- Worker crash, bounded restart, and crash-loop stop;
- graceful drain, grace expiry, hard-stop expiry, and repeated shutdown signal;
- no leaked tasks, connections, files, executors, or request contexts after shutdown;
- race and deadlock stress with repeatable diagnostics.

## Explicitly unresolved

This ADR does not decide:

- the minimum supported Python version;
- public class and method names for Scope, Deadline, limiter, or cancellation APIs;
- specific default numeric limits;
- a mandatory third-party event loop;
- low-level listener distribution strategy between Workers;
- HTTP/2 and HTTP/3 multiplexing;
- exact source directory or package boundaries.

## Consequences

### Benefits

- predictable request ownership and cleanup;
- bounded resource use and explicit overload behavior;
- consistent single-Worker and multi-Worker semantics;
- safer shutdown, cancellation, and background work;
- cross-platform architecture without fork-only assumptions;
- testable concurrency contracts before optimization.

### Costs

- more explicit runtime bookkeeping;
- route, executor, task, and transport capacity configuration;
- background work must use framework registration rather than raw fire-and-forget tasks;
- CPU and blocking integrations require explicit isolation;
- HTTP/1.1 pipelined concurrency is intentionally not supported initially.

## Rejected alternatives

- one thread per request;
- unbounded `create_task`-style fire-and-forget work;
- one global mutable request context;
- unlimited executor queues;
- refreshing the full timeout duration at every nested layer;
- concurrently executing multiple HTTP/1.1 requests on one connection in the initial runtime;
- infinite Worker restart loops;
- shutdown that merely stops the event loop without draining and cleanup;
- requiring a third-party event loop for correctness.
