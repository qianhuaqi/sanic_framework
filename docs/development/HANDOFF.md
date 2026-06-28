# Development Handoff

Updated at: 2026-06-28
Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Phase: P0 - Architecture Decision Review and Blueprint Consolidation
Parent Issue: #25
Active decision Issue: none
Active decision branch: none
Baseline: latest accepted `main`
Status: P0-D4 accepted; awaiting P0-D5

## Accepted decisions

- P0-D1: repository and development concurrency through ADR-001 / PR #32.
- P0-D2: runtime concurrency through ADR-002 / PR #35.
- P0-D3: package and component layout through ADR-003 / PR #38.
- P0-D4: Application Kernel and request pipeline through ADR-004 / PR #41.

P0-D4 merge commit:

```text
bb78918dc2bc92dd49c34258e3707abd37274f12
```

## Confirmed Application model

```text
Public LingShu facade
└─ private Application Kernel
   └─ immutable Application Plan
```

Lifecycle:

```text
CREATED
→ CONFIGURING
→ FROZEN
→ STARTING
→ RUNNING
→ DRAINING
→ STOPPING
→ STOPPED
```

Registration is allowed only before freeze. Freeze validates the full revision and atomically publishes an immutable plan. Freeze failure publishes no partial state. Running plan mutation is prohibited.

## Confirmed request path

```text
protocol acceptance
→ Request Scope and absolute Deadline
→ identities and Runtime Record
→ immutable Request and bounded body stream
→ application admission
→ application Middleware
→ route match
→ route admission/capabilities
→ route Middleware
→ asynchronous Handler
→ one-time Response normalization
→ Middleware reverse unwind
→ exception fallback when needed
→ Response preparation
→ response-head commit
→ body/stream transmission with backpressure
→ Runtime Record finalization
→ request-owned task cleanup
→ resource/context release
```

## Confirmed contracts

- Handler receives one explicit Request and is asynchronous initially.
- Application and route Middleware use deterministic onion ordering.
- `call_next` is single-use and Scope-bound.
- Request metadata is immutable.
- Request state is Scope-local.
- Request body is bounded, backpressured, and single-consumer.
- `Response`, `str`, and bytes-like values are initial supported Handler results.
- `None`, tuple magic, arbitrary iterators, and unknown values are rejected by default.
- Response state is `NEW → PREPARED → COMMITTED → COMPLETED/ABORTED`.
- Status and headers are immutable after commit.
- No second response can replace a committed response.
- Exception mapping order is route, application, `HTTPException`, then safe default before commit.
- Extensions contribute during configuration and are compiled at freeze.
- Extensions cannot mutate registries while running.

## Confirmed minimum public facade

```python
from lingshu import LingShu, Request, Response, HTTPException
```

Example shape:

```python
app = LingShu()

@app.get("/")
async def index(request: Request) -> Response:
    return Response.text("hello")
```

## Intentionally deferred

- configuration reload and multi-Worker plan rollout;
- full exception taxonomy and error body schema;
- identifier formats;
- JSON and other serialization rules;
- cookies, forms, multipart, uploads, and content negotiation;
- automatic HEAD/OPTIONS;
- host routing, reverse routing, mounting, and sub-applications;
- public run/serve and CLI behavior;
- sync Handler adaptation;
- dependency injection;
- OpenAPI and official capabilities;
- exact media types, limits, and timeouts;
- Python/platform support and build backend.

## Next decision

P0-D5 should consolidate:

- identifier standards and correlation;
- exception taxonomy and safe client errors;
- configuration source/precedence/validation/version/reload/rollback rules;
- serialization and content negotiation baseline;
- Runtime Record envelope, storage budgets, retention, disk safety, and recovery;
- common telemetry fields.

## Verification

P0-D4 added architecture and governance documentation only. No production source, package skeleton, dependency, or publishing configuration was created.

P1 remains blocked.
