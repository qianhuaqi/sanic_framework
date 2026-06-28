# Current Phase

Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Current phase: P0 - Architecture Decision Review and Blueprint Consolidation
Phase type: non-implementation architecture and governance
Accepted baseline: latest accepted `main`
Active decision branch: none
Active decision Issue: none
Parent architecture Issue: #25
Status: P0-D5 accepted; awaiting next architecture decision
Next phase allowed: no

## Foundational fact

LingShu is a completely new and independently implemented Python Web/API framework. It does not depend on Sanic, FastAPI, Flask, Django, Starlette, or another upper-level Web framework. The archived implementation creates no compatibility obligation.

## Completed decisions

### P0-D1

Repository and concurrent-development governance accepted through ADR-001 / PR #32.

### P0-D2

Runtime concurrency accepted through ADR-002 / PR #35.

### P0-D3

Package and component layout accepted through ADR-003 / PR #38.

```text
Distribution:    lingshu
Import package:  lingshu
Production code: lingshu/
src layout:      prohibited
```

### P0-D4

Application Kernel, request pipeline, and minimum public facade accepted through ADR-004 / PR #41.

```python
from lingshu import LingShu, Request, Response, HTTPException
```

### P0-D5

Hardening Foundations accepted through ADR-005 / PR #44 at merge commit `704146f103e2daafac7e489951497411821e9ba9`.

Confirmed:

- separate UTC wall-clock and monotonic time semantics;
- typed opaque Request, Connection, Trace, Operation, Worker, Record, and Revision identifiers;
- internal RequestId cannot be replaced by inbound correlation;
- stable dotted error codes and safe `application/problem+json` responses;
- deterministic configuration precedence, schema versions, secret redaction, immutable snapshots, reload, and rollback;
- strict bounded UTF-8 JSON and explicit content negotiation;
- Runtime Record reservation before business handling;
- versioned append-only event envelopes and JSON Lines local segments;
- declared durability, bounded queues/storage, disk watermarks, retention, and crash recovery;
- common telemetry fields, shared redaction classes, and metric-cardinality restrictions;
- the former Hardening Checklist is now a Verified integration record, not a second architecture source.

## Still unresolved

- public server startup and shutdown API;
- CLI command model, application discovery, development reload, and exit codes;
- minimum Python version and supported operating systems;
- build backend, authoritative version source, package metadata, and CI matrix;
- default numeric limits and environment profiles;
- automatic HEAD/OPTIONS, host routing, reverse routing, mounts, and sub-applications;
- forms, multipart, uploads, compression, and streaming serialization;
- sync Handler adaptation and dependency injection;
- official capabilities and extensions;
- release, compatibility, license, contribution, security, changelog, and code-of-conduct policy;
- final P0 freeze and P1 implementation plan.

## Recommended next decision

P0-D6 should decide the executable and packaging baseline:

1. public `serve`/startup surface and ownership between Application, Server, and CLI;
2. CLI command grammar and `module:app` discovery;
3. production versus development execution and reload boundaries;
4. Worker/process startup options and graceful signal behavior;
5. minimum Python version and platform support matrix;
6. build backend and authoritative version source;
7. package metadata, wheel/sdist, console entry point, and CI compatibility matrix;
8. configuration profiles and exit-code contract;
9. implementation tests for startup, import, discovery, signal, packaging, and clean installation.

## Out of scope

- creating production package files or directories;
- implementing any framework component;
- adding runtime dependencies;
- publishing packages;
- starting P1.

P1 remains blocked until all P0 exit conditions are satisfied and the project lead explicitly authorizes it.
