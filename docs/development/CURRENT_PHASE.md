# Current Phase

Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Current phase: P0 - Architecture Decision Review and Blueprint Consolidation
Phase type: non-implementation architecture and governance
Accepted baseline: latest accepted `main`
Active decision branch: none
Active decision Issue: none
Parent architecture Issue: #25
Status: P0-D4 accepted; awaiting next architecture decision
Next phase allowed: no

## Foundational fact

LingShu is a completely new, independently implemented Python Web/API framework.

It does not depend on Sanic, FastAPI, Flask, Django, Starlette, or another upper-level Web framework. The archived implementation creates no compatibility obligation.

## Completed decisions

### P0-D1: Single repository and development concurrency

Accepted through ADR-001 and PR #32.

### P0-D2: Runtime concurrency

Accepted through ADR-002 and PR #35.

### P0-D3: Package and component layout

Accepted through ADR-003 and PR #38.

```text
Distribution:    lingshu
Import package:  lingshu
Production code: lingshu/
src layout:      prohibited
```

### P0-D4: Application Kernel and request pipeline

Accepted through ADR-004 and PR #41 at merge commit `bb78918dc2bc92dd49c34258e3707abd37274f12`.

Confirmed:

- public `LingShu` composition root and private low-level Application Kernel;
- lifecycle `CREATED → CONFIGURING → FROZEN → STARTING → RUNNING → DRAINING → STOPPING → STOPPED`;
- immutable Application Revision and atomic Application Plan publication;
- no route, middleware, exception, extension, or configuration mutation after freeze;
- asynchronous handler contract with explicit Request input;
- deterministic application and route middleware onion ordering;
- canonical twenty-stage request pipeline;
- immutable Request metadata, scoped state, and bounded single-consumer body;
- exactly-once handler return normalization;
- Response lifecycle `NEW → PREPARED → COMMITTED → COMPLETED/ABORTED`;
- no status/header mutation or replacement response after commit;
- deterministic route/application/HTTPException/default exception resolution;
- extension contributions compiled before startup and immutable while running;
- minimum root exports `LingShu`, `Request`, `Response`, and `HTTPException`.

## Still unresolved

- identifier formats and propagation rules;
- complete exception taxonomy and safe client-error schema;
- configuration schema, source precedence, versioning, reload, and rollback;
- JSON and general serialization/content-negotiation rules;
- cookies, forms, multipart, uploads, and body-decoding APIs;
- Runtime Record storage format, budgets, retention, disk safety, and recovery;
- automatic HEAD/OPTIONS, host routing, reverse routing, mounts, and sub-applications;
- public run/serve and CLI behavior;
- Python and platform support range;
- build backend and version-source mechanism;
- official capabilities and extensions;
- release, compatibility, license, contribution, and security policy.

## Recommended next decision

P0-D5 should consolidate the remaining hardening foundations:

1. Request, Connection, Trace, Operation, Worker, and Revision identifier standards;
2. exception taxonomy, safe messages, error codes, and redaction;
3. configuration sources, precedence, validation, immutability, versioning, reload, and rollback;
4. serialization and content-negotiation baseline;
5. Runtime Record event envelope, storage budgets, retention, disk safety, failure behavior, and crash recovery;
6. common telemetry fields and correlation rules.

## Out of scope

- creating production package files or directories;
- implementing any framework component;
- adding runtime dependencies;
- publishing packages;
- starting P1.

P1 remains blocked until all P0 exit conditions are satisfied and the project lead explicitly authorizes it.
