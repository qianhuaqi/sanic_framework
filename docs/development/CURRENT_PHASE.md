# Current Phase

Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Current phase: P0-D4 - Application Kernel, Request Pipeline, and Minimum Public API
Phase type: non-implementation architecture and governance
Accepted baseline: latest accepted `main`
Active decision branch: `human/dodo/phase-p0-d4-application-kernel`
Active decision Issue: #40
Parent architecture Issue: #25
Status: proposed architecture under project-lead review
Next phase allowed: no

## Foundational fact

LingShu is a completely new, independently implemented Python Web/API framework.

It does not depend on Sanic, FastAPI, Flask, Django, Starlette, or another upper-level Web framework. The archived implementation creates no compatibility obligation.

## Completed decisions

### P0-D1

Single repository and development concurrency are accepted through ADR-001 and PR #32.

### P0-D2

Runtime concurrency is accepted through ADR-002 and PR #35.

### P0-D3

Package, source layout, and component boundaries are accepted through ADR-003 and PR #38.

Confirmed package baseline:

```text
Distribution:    lingshu
Import package:  lingshu
Production code: lingshu/
src layout:      prohibited
```

## Active proposal: P0-D4

The proposal defines:

- public `LingShu` composition root and internal Application Kernel;
- lifecycle `CREATED → CONFIGURING → FROZEN → STARTING → RUNNING → DRAINING → STOPPING → STOPPED`;
- immutable Application Revision and compiled Application Plan;
- route, middleware, extension, configuration, and exception registration only before freeze;
- no partial plan publication after freeze failure;
- asynchronous handler contract with explicit Request input;
- deterministic application and route middleware onion ordering;
- fixed request pipeline from protocol acceptance through Scope cleanup;
- immutable Request metadata, request-scoped state, and bounded single-consumer body;
- one-time handler return normalization;
- Response states `NEW → PREPARED → COMMITTED → COMPLETED/ABORTED`;
- no status/header mutation or second response after commit;
- deterministic exception mapper resolution;
- extension contribution at configuration/freeze time and immutable request-time participation;
- minimum root exports: `LingShu`, `Request`, `Response`, and `HTTPException`.

Detailed proposal:

- `docs/decisions/ADR-004-application-kernel-request-pipeline-and-public-api.md`
- `docs/architecture/APPLICATION_KERNEL_AND_REQUEST_PIPELINE.md`

## Explicitly unresolved

P0-D4 does not decide:

- full configuration hot reload and multi-Worker rollout;
- complete exception taxonomy and error payload schema;
- identifier formats;
- JSON/form/multipart/upload APIs;
- automatic `HEAD` and `OPTIONS`;
- host routing, reverse routing, mounts, and sub-applications;
- server `run`/`serve` and CLI details;
- synchronous handler adaptation;
- dependency injection;
- OpenAPI and official extension implementations;
- exact numeric limits, timeouts, and media-type defaults;
- Python/platform support and build backend.

## Current objective

1. review ADR-004 and the detailed pipeline contract;
2. verify the state and freeze boundaries;
3. verify Middleware and exception ordering;
4. verify Request/Response ownership and commit semantics;
5. verify the minimal public API remains small;
6. open a documentation-only Pull Request;
7. keep P1 blocked.

## Out of scope

- creating production package files or directories;
- implementing Kernel, Router, Middleware, Request, Response, Server, Record, CLI, or extensions;
- adding runtime dependencies;
- publishing packages;
- starting P1.

## Exit conditions for P0-D4

1. ADR-004 and detailed request-pipeline documentation are reviewed and merged;
2. Application states and freeze semantics are explicit;
3. Route, Middleware, Handler, Request, Response, and Exception contracts are explicit;
4. request stage ordering is deterministic and testable;
5. commit and post-commit failure semantics are explicit;
6. the minimum public facade is explicit;
7. deferred decisions remain unresolved;
8. the project lead performs the final merge.

P0 continues after P0-D4. P1 remains blocked.
