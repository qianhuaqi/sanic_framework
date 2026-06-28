# LingShu Development Constitution

- Status: P0 candidate
- Applies to: the greenfield LingShu framework repository

## 1. Project identity

LingShu is an independently implemented Python Web/API framework. It is not a wrapper around, migration from, or compatibility layer for Sanic or any other upper-level Web framework.

## 2. Authority

- The project lead decides scope and performs final merges.
- Architecture changes require a GitHub Issue and ADR.
- Developers implement only an approved phase Issue.
- The implementation author cannot self-accept the phase.

## 3. Greenfield policy

Before v1.0:

- legacy APIs have no automatic compatibility guarantee;
- obsolete code may be redesigned or removed;
- no permanent compatibility package is created without a real released consumer and an approved ADR;
- old repository source and tests are not implementation baselines.

## 4. Architecture policy

- Core mechanisms and optional policies must remain separate.
- Dependency direction must be explicit and cycle-free.
- Runtime state must be app-, worker-, request-, and operation-scoped as appropriate.
- Queues, buffers, requests, retries, timeouts, files, and background tasks must be bounded.
- Startup failure must roll back acquired resources.
- Cancellation must propagate and cleanup must be deterministic.
- Security, correctness, and observability take priority over speculative performance.

## 5. Phase workflow

1. Architecture or implementation Issue.
2. Dedicated branch.
3. Work limited to Issue scope.
4. Required tests and evidence.
5. Independent review.
6. Project-lead merge.
7. Next phase starts only after merge.

## 6. Prohibited actions

- Direct commits to `main`.
- Automatic merge.
- Force push or history rewriting.
- Starting implementation while P0 is not accepted.
- Introducing Sanic, FastAPI, Flask, Django, Starlette, or another upper-level Web framework dependency.
- Reintroducing legacy compatibility requirements without approved evidence and ADR.
