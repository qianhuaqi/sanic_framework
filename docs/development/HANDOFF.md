# Development Handoff

Updated at: 2026-06-28
Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Phase: P0-D4 - Application Kernel, Request Pipeline, and Minimum Public API
Parent Issue: #25
Active decision Issue: #40
Active decision branch: `human/dodo/phase-p0-d4-application-kernel`
Baseline: latest accepted `main`
Status: proposed architecture ready for review

## Accepted decisions

- P0-D1: single repository and development concurrency through ADR-001 / PR #32.
- P0-D2: runtime concurrency through ADR-002 / PR #35.
- P0-D3: package and component layout through ADR-003 / PR #38.

## P0-D4 proposal completed on this branch

- Added `ADR-004-application-kernel-request-pipeline-and-public-api.md`.
- Added `APPLICATION_KERNEL_AND_REQUEST_PIPELINE.md`.
- Defined public `LingShu` composition root and private low-level Application Kernel.
- Defined Application states and legal mutation windows.
- Defined immutable Application Revision and atomic freeze publication.
- Defined route declaration, conflict validation, and immutable compiled Router.
- Defined asynchronous handler contract with explicit Request input.
- Defined deterministic application and route Middleware onion ordering.
- Defined the exact twenty-stage request pipeline.
- Defined immutable Request metadata, scoped state, and bounded single-consumer body.
- Defined one-time handler return normalization and rejected tuple/None magic.
- Defined Response state and commit semantics.
- Defined exception mapper resolution before and after commit.
- Defined extension contribution, startup, request-time, and reverse-shutdown boundaries.
- Proposed minimum root exports: `LingShu`, `Request`, `Response`, `HTTPException`.
- Defined state-machine, contract, leak, ordering, commit, and import-side-effect tests.

## Proposed application lifecycle

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

No route, Middleware, Extension, exception mapper, or configuration registry mutation is allowed after freeze.

## Proposed request path

```text
protocol acceptance
→ Request Scope / Deadline
→ identities / Runtime Record
→ Request construction
→ application admission
→ application Middleware
→ route match
→ route admission
→ route Middleware
→ async Handler
→ Response normalization
→ Middleware unwind
→ exception fallback
→ Response prepare
→ commit
→ body write/stream
→ record finalization
→ Scope cleanup
```

## Proposed public facade

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

- configuration hot reload and multi-Worker rollout;
- full exception taxonomy and error body schema;
- identifier formats;
- JSON/form/multipart/upload APIs;
- automatic `HEAD` and `OPTIONS`;
- host routing, reverse routing, mounts, and sub-applications;
- server `run`/`serve` and CLI semantics;
- sync handler adaptation;
- dependency injection;
- OpenAPI and official integrations;
- exact numeric defaults;
- Python/platform support and build backend.

## Verification

This branch contains architecture and governance documentation only. It adds no production source, package skeleton, dependency, or publishing configuration.

Review must verify:

- lower Core does not depend on Server through the public facade;
- failed freeze cannot publish a partial plan;
- running plan mutation is impossible;
- Middleware order is deterministic;
- Request body and state remain Scope-owned;
- Response cannot be replaced after commit;
- cancellation is not converted into an ordinary error response;
- extensions cannot mutate registries during request handling;
- the public root export surface remains minimal;
- P1 remains blocked.

## Next action

Review and merge the P0-D4 decision Pull Request only if the Kernel and request-pipeline contract is accepted. Do not start production implementation.
