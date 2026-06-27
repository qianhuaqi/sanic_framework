# Current Phase

Project: LingShu Framework
Current phase: C1 - request execution foundation and lifecycle
Current branch: codex/phase-c1-request-runtime
Current issue: #12
Current PR: #13
Status: implementation allowed within C1 scope
Next phase allowed: no

## Accepted Baseline

- Phase A accepted and merged.
- Phase B accepted and merged through PR #8.
- Phase C0 research convergence accepted and merged through PR #11.
- C0 merge commit: `d571602cb0e83b7abe49a3f1b53e43dbeb2d2aa8`.
- Phase B tests previously recorded: 125 passed, 0 failed, 1 skipped.

## Phase Goal

Build the request execution foundation required by later security, database, Schema, idempotency and extension work:

```text
RequestExecutionContext
compiled RoutePolicy skeleton
deadline/cancellation
TaskRegistry
health/live/ready/drain
ShutdownCoordinator
```

The full specification and acceptance contract are in Issue #12.

## Required Work

### Request execution context

- request_id;
- trace_id field/propagation hook only;
- optional operation_id;
- compiled route policy;
- absolute monotonic deadline;
- cancellation reason;
- lifecycle state;
- ContextVar isolation and guaranteed reset.

### RoutePolicy compiler skeleton

- explicit global -> blueprint/controller -> route precedence;
- immutable compiled policy;
- startup validation;
- current fields limited to public/auth_required compatibility, maintenance_check, timeout, body_limit metadata and audit_level metadata;
- every route receives a compiled policy.

### Deadline and cancellation

- absolute deadline;
- remaining budget;
- stable cancellation reasons;
- cleanup in finally;
- do not swallow cancellation.

### TaskRegistry

- strong task references;
- spawn/list/cancel/cancel_all/shutdown_and_wait;
- consume task exceptions;
- remove completed tasks;
- cancellation must be awaited;
- no default detach.

### Lifecycle

```text
starting -> ready -> draining -> stopping -> stopped
```

- `/live`;
- `/ready`;
- basic `/health`;
- drain rejects new business work;
- cleanup callbacks run in reverse order;
- shutdown budgets and idempotent repeated shutdown.

## Mandatory Tests

- 100 and 1000 concurrent request contexts do not cross-contaminate;
- multi-app isolation;
- reset after normal return, exception, cancellation and timeout;
- deadline remaining budget decreases correctly;
- parent deadline constrains child operations;
- route policy precedence, immutability and invalid-combination failures;
- every route has a compiled policy;
- TaskRegistry holds strong references, consumes errors and awaits cancellation;
- lifecycle state transition matrix;
- drain/readiness behavior;
- reverse cleanup order and partial cleanup failure;
- shutdown idempotency and total budget;
- existing full tests, wheel/sdist and generated-project smoke remain passing.

Concurrency tests must use deterministic Event/Barrier/Fake Clock techniques rather than random sleep.

## Current Prohibitions

Do not implement or refactor the following in C1:

```text
JWT/API Key/Session authentication
resource authorization and real TenantContext resolution
HMAC signing, nonce and replay protection
rate limiting, concurrency store or idempotency store
MySQL/SQLite/MongoDB/Redis backend redesign
Pydantic Schema facade
OpenAPI 3.1 compiler or TypeScript SDK
full DI container or Extension Manifest runtime
Outbox, Audit implementation or OTel exporter
lingshu-ms, Go runtime, Vue runtime or device gateway
```

Also prohibited:

- no giant runtime.py;
- no business imports from `lingshu.system`;
- no unowned `asyncio.create_task()`;
- no swallowing `CancelledError`;
- no unbounded queues;
- no secrets, private paths, credentials or network addresses;
- no starting C2 before independent C1 acceptance.

If a later-phase need is discovered, document it in the relevant issue; do not implement it in this branch.

## PR Requirements

PR title:

```text
feat: add request execution context and lifecycle foundation
```

PR body must include:

```text
Refs #12
implementation summary
public and internal API list
lifecycle/state-machine explanation
test results and new test list
explicit non-goals
risks and later extension points
```

Codex must not merge the PR.

## Acceptance Owner

- Xiao Gu performs independent review and records the result in GitHub.
- GitHub branch, Issue #12, PR, commits, tests, ADRs and this file are the source of truth.
- Local chat state is not evidence of completion.

## Branch And Tracking

- Branch: `codex/phase-c1-request-runtime`
- Issue: `#12`
- Pull request: `#13`
