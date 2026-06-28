# LingShu Runtime Concurrency Model

- Status: Proposed for P0-D2
- Decision Issue: #34
- Parent Issue: #25
- Related ADR: `docs/decisions/ADR-002-runtime-concurrency-model.md`

## 1. Purpose

This document turns the P0-D2 runtime concurrency decision into an implementable architecture contract without creating production code.

It defines:

- ownership;
- concurrency limits;
- admission and backpressure;
- Deadline and cancellation;
- blocking-work isolation;
- Worker lifecycle;
- graceful shutdown;
- observability;
- acceptance testing.

## 2. Runtime topology

```text
Supervisor Process
├─ Worker Process 1
│  └─ one event loop
│     └─ one Application Runtime
│        ├─ Listener tasks
│        ├─ Application background tasks
│        ├─ Connection scopes
│        │  └─ Request scopes
│        │     └─ Operation scopes
│        └─ bounded executors and telemetry pipelines
├─ Worker Process 2
│  └─ one event loop
│     └─ one Application Runtime
└─ Worker Process N
   └─ one event loop
      └─ one Application Runtime
```

The Supervisor is not a request execution environment. It coordinates Workers, readiness, signals, restart policy, and process exit.

## 3. Ownership model

### 3.1 Supervisor ownership

The Supervisor owns:

- Worker process handles;
- restart budgets;
- readiness aggregation;
- shutdown orchestration;
- final process exit status;
- process-level control events.

### 3.2 Worker ownership

A Worker owns:

- one event loop;
- one application runtime;
- listener or accepted-connection resources assigned to it;
- connection scopes;
- request scopes;
- application background tasks;
- thread and process executors;
- Worker-local metrics, logs, and Runtime Record queues.

### 3.3 Application ownership

The application runtime owns:

- application lifecycle state;
- extension lifecycle;
- route and middleware plan;
- application task registry;
- global and route capacity limiters;
- application health state.

### 3.4 Connection ownership

A connection Scope owns:

- transport reader and writer;
- connection identity;
- parser state;
- bounded read-ahead buffer;
- keep-alive state;
- current request Scope, if any;
- idle, read-progress, and write-progress Deadlines.

### 3.5 Request ownership

A request Scope owns:

- Request ID;
- request context;
- absolute Deadline;
- cancellation reason;
- route and middleware execution;
- request body stream;
- response state;
- operation children;
- Runtime Record.

### 3.6 Operation ownership

An operation Scope represents a child call such as:

- database query;
- cache call;
- outbound HTTP call;
- file operation;
- extension operation;
- blocking executor submission;
- explicitly grouped child task.

Operations inherit and may only shorten the parent Deadline.

## 4. Task classes

### 4.1 Request-owned tasks

Default for tasks created during request processing.

Properties:

- inherit request cancellation;
- cannot outlive request completion;
- are awaited during request cleanup;
- failure contributes to request outcome or is explicitly handled;
- remain visible in Runtime Record.

### 4.2 Application-owned background tasks

Long-lived tasks registered during application lifecycle.

Required metadata:

```text
name
owner
start_phase
stop_policy
failure_policy
restart_policy
max_restarts
restart_window
deadline
shutdown_grace
context_policy
```

### 4.3 Worker-owned infrastructure tasks

Examples:

- listener loop;
- telemetry drain;
- Runtime Record writer;
- health reporting;
- Worker control channel.

These tasks are framework-managed and stop before Worker exit.

### 4.4 Prohibited orphan tasks

A task with no registered owner is invalid.

The runtime must detect tasks left outside managed Scopes during tests and shutdown. Production behavior must at minimum record and cancel them; strict mode may treat them as fatal runtime defects.

## 5. HTTP/1.1 concurrency

### 5.1 Per-connection execution

One HTTP/1.1 connection executes one request at a time.

```text
connection A: request A1 → response A1 → request A2 → response A2
connection B: request B1 runs concurrently with A1
```

### 5.2 Pipelining

The initial runtime does not concurrently dispatch pipelined requests.

Additional request bytes may remain in a bounded parser/read-ahead buffer. They are not promoted to a new request Scope until the previous response is complete and connection policy allows reuse.

Overflow, ambiguous framing, or policy violation causes rejection or connection close.

### 5.3 Streaming

Request and response streaming are flow-controlled.

- body producers cannot outrun bounded consumer buffers;
- response producers await transport capacity;
- slow readers consume write-progress budget;
- disconnect cancels the owning request and descendants.

## 6. Capacity hierarchy

Each capacity control has:

```text
limit
current_usage
bounded_waiters
wait_deadline
rejection_reason
metrics
```

Recommended control layers:

1. process Worker count;
2. per-Worker active connections;
3. per-Worker active requests;
4. per-application active requests;
5. per-route active requests;
6. application background tasks;
7. thread executor active and queued work;
8. process executor active and queued work;
9. outbound dependency concurrency;
10. telemetry and Runtime Record queues.

Limits are configurable, but no limit may default to an implicit unbounded queue.

## 7. Admission outcomes

Admission produces one of:

- admitted immediately;
- waiting within a bounded queue;
- rejected because capacity is full;
- rejected because wait Deadline expired;
- cancelled while waiting;
- rejected because the service is draining;
- rejected because a dependency is unhealthy.

Every outcome is observable and recorded.

## 8. Backpressure chain

```text
transport capacity
    ↓
parser and body-buffer capacity
    ↓
connection/request admission
    ↓
route and application capacity
    ↓
executor/dependency capacity
    ↓
response transport capacity
```

When a lower layer is saturated, pressure propagates upward. The framework pauses production or reading rather than accumulating unlimited intermediate work.

## 9. Deadline model

A Deadline is represented conceptually as an absolute monotonic point:

```text
deadline_at = monotonic_now + allowed_duration
remaining = deadline_at - monotonic_now
```

Rules:

- a child Deadline is `min(parent_deadline, requested_child_deadline)`;
- zero or negative remaining budget fails immediately;
- wall-clock changes do not extend or shorten runtime budgets;
- cleanup may have a distinct bounded cleanup budget, never an unlimited shield;
- queue wait time counts against the request budget unless a decision explicitly defines a pre-request admission phase.

## 10. Cancellation model

### 10.1 Cancellation reasons

Minimum reason taxonomy:

```text
CLIENT_DISCONNECT
REQUEST_DEADLINE
SERVER_DRAINING
WORKER_STOPPING
PARENT_CANCELLED
APPLICATION_CANCELLED
ADMISSION_REJECTED
DEPENDENCY_CANCELLED
```

### 10.2 Propagation

```text
owner cancellation
    ↓
child scopes receive cancellation
    ↓
child cleanup runs within bounded budget
    ↓
child completion is awaited
    ↓
owner cleanup completes
```

### 10.3 Cancellation handling rules

- cancellation cannot be converted into success accidentally;
- broad exception handlers must not hide cancellation;
- cleanup failures are recorded separately from the original cancellation;
- shielding requires an explicit bounded reason;
- cancellation after response commit is still recorded even if the status code cannot change.

## 11. Blocking-work isolation

### 11.1 Thread executor

For blocking I/O that cannot be made asynchronous.

Required controls:

- maximum workers;
- bounded submission queue;
- admission timeout;
- task identity and owner;
- completion and abandoned-result accounting;
- shutdown grace.

### 11.2 Process executor

For CPU-heavy work where process isolation is appropriate.

Required controls:

- bounded process count;
- bounded queue;
- serialization limits;
- task Deadline;
- child process health;
- termination policy after hard-stop Deadline.

### 11.3 Cancellation limitation

Already-running thread work may not be forcibly stopped safely. The owning request may cancel and discard the result, but the thread work remains tracked until it returns. New work must be rejected when executor capacity is exhausted.

## 12. Worker model

### 12.1 Reference semantics

Single-Worker mode defines correctness semantics.

Multi-Worker mode scales throughput without changing:

- Request and Response contracts;
- lifecycle ordering;
- extension semantics;
- cancellation reasons;
- Runtime Record meaning;
- shutdown guarantees.

### 12.2 State isolation

Workers do not share mutable Python objects. Any cross-Worker state uses an explicit external or IPC mechanism with its own consistency semantics.

### 12.3 Restart policy

A restart policy includes:

```text
max_restarts
restart_window
minimum_backoff
maximum_backoff
stable_period_reset
crash_loop_action
```

A Worker crash loop marks the service unhealthy and stops automatic restarts after budget exhaustion.

## 13. Runtime state machine

```text
CREATED
  ↓
STARTING
  ↓
RUNNING
  ↓
DRAINING
  ↓
STOPPING
  ↓
STOPPED
```

Failure paths may move from STARTING, RUNNING, or DRAINING into STOPPING.

Illegal transitions fail explicitly and are recorded.

## 14. Graceful shutdown sequence

### 14.1 Supervisor

1. receive shutdown signal;
2. mark aggregate readiness false;
3. command Workers to drain;
4. wait for graceful Worker completion;
5. send cancellation/stop escalation after grace expiry;
6. terminate after hard-stop expiry;
7. aggregate exit and forced-stop results.

### 14.2 Worker

1. mark Worker not ready;
2. stop listener admission;
3. stop new request and background-task admission;
4. drain active requests and response streams;
5. cancel remaining request and operation Scopes after grace expiry;
6. stop background tasks;
7. close extensions in reverse order;
8. flush records and telemetry within bounded budgets;
9. stop executors and infrastructure tasks;
10. close transports;
11. report final state and exit.

### 14.3 Repeated shutdown signal

A second signal may request immediate escalation. The runtime still records which cleanup stages were skipped or incomplete.

## 15. Runtime Record requirements

Concurrent Runtime Record events must preserve:

- request and operation identity;
- parent-child relation;
- monotonic ordering fields;
- queue and admission events;
- cancellation source;
- response commit point;
- cleanup outcome;
- truncation or drop information.

Cross-task event order is not inferred from wall-clock timestamps alone.

## 16. Observability contract

Minimum metric groups:

### Connections

```text
accepted
active
closed
idle_timeout
read_timeout
write_timeout
protocol_rejected
```

### Requests

```text
admitted
queued
active
completed
rejected
timeout
client_disconnect
cancelled
```

### Tasks

```text
active_by_scope
created
completed
failed
cancelled
orphan_detected
```

### Executors

```text
active
queue_depth
queue_rejected
timeout
abandoned_result
shutdown_incomplete
```

### Workers

```text
starting
ready
draining
stopped
crashed
restarted
restart_budget_exhausted
forced_terminated
```

### Runtime Record

```text
queue_depth
written
truncated
dropped
write_failed
flush_timeout
```

## 17. Test architecture

### Deterministic tests

- fake monotonic clock;
- controllable task barriers;
- bounded test transports;
- deterministic cancellation injection;
- repeatable Worker crash simulation;
- resource snapshots before and after tests.

### Stress tests

- repeated high-concurrency cycles;
- randomized cancellation points;
- slow-client mixes;
- executor saturation;
- shutdown under load;
- restart storms within configured budgets.

### Leak gates

After test completion:

- no unexpected live tasks;
- no open transports;
- no retained request contexts;
- no unclosed executors;
- no pending Runtime Record events outside declared failure simulation.

## 18. Decisions intentionally deferred

- final Python minimum version;
- exact public API names;
- exact default capacities and timeout values;
- listener socket sharing strategy;
- required or optional `uvloop` support;
- HTTP/2 stream concurrency;
- HTTP/3 and QUIC;
- final physical module and distribution placement.

## 19. Acceptance rule

Merging the P0-D2 decision PR accepts the semantics in ADR-002 and this document. Production implementation remains prohibited until the complete P0 Blueprint is frozen and P1 is explicitly authorized.
