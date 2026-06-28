# Current Phase

Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Current phase: P0-D5 - Hardening Foundations
Phase type: non-implementation architecture and governance
Accepted baseline: latest accepted `main`
Active decision branch: `human/dodo/phase-p0-d5-hardening-foundations`
Active decision Issue: #43
Parent architecture Issue: #25
Status: proposed architecture under project-lead review
Next phase allowed: no

## Foundational fact

LingShu is a completely new, independently implemented Python Web/API framework.

It does not depend on Sanic, FastAPI, Flask, Django, Starlette, or another upper-level Web framework. The archived implementation creates no compatibility obligation.

## Completed decisions

### P0-D1

Repository and development concurrency accepted through ADR-001 / PR #32.

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

Application Kernel and request pipeline accepted through ADR-004 / PR #41.

Confirmed minimum facade:

```python
from lingshu import LingShu, Request, Response, HTTPException
```

## Active proposal: P0-D5

The proposal defines:

- separate UTC wall-clock and process-local monotonic time semantics;
- typed 128-bit opaque Request, Connection, Trace, Operation, Worker, and Record identifiers;
- SHA-256 Application Revision identifiers;
- internal Request ID generation regardless of inbound correlation headers;
- stable lowercase dotted framework error codes;
- safe `application/problem+json` client errors;
- configuration precedence, schema versioning, secret redaction, immutable Snapshots, reload, and rollback;
- strict UTF-8 JSON, duplicate-key and NaN/Infinity rejection, bounded parsing, and explicit custom serializers;
- 406/415 content-negotiation behavior;
- Runtime Record reservation before business handling;
- versioned append-only event envelopes;
- JSON Lines local segments, atomic manifests, durability policies, budgets, retention, disk watermarks, and crash recovery;
- shared telemetry fields, redaction classes, and metric-cardinality rules;
- conversion of the old Hardening Checklist into an integration verification record.

Detailed proposal:

- `docs/decisions/ADR-005-hardening-foundations.md`
- `docs/architecture/HARDENING_FOUNDATIONS.md`

## Explicitly unresolved

P0-D5 does not decide:

- exact numeric limits, retention periods, or fsync frequency;
- configuration file syntax;
- secret-provider implementations;
- multi-Worker reload transport or consensus mechanism;
- full form, multipart, upload, compression, and streaming serialization;
- concrete logging, metrics, tracing, database, or object-storage backends;
- OpenTelemetry integration;
- Python/platform support and build backend;
- public run/serve and CLI semantics;
- official business capabilities and extensions;
- release and public governance policy.

## Current objective

1. review ADR-005 and the detailed hardening contract;
2. verify identifier trust boundaries and correlation rules;
3. verify exception safety and stable code rules;
4. verify configuration reload has no partial visibility;
5. verify strict serialization and negotiation behavior;
6. verify Runtime Record failure, disk, retention, and recovery semantics;
7. verify telemetry redaction and cardinality rules;
8. open a documentation-only Pull Request;
9. keep P1 blocked.

## Out of scope

- creating production package files or directories;
- implementing identifiers, configuration, serializers, records, or telemetry;
- adding runtime dependencies;
- publishing packages;
- starting P1.

## Exit conditions for P0-D5

1. ADR-005 and `HARDENING_FOUNDATIONS.md` are reviewed and merged;
2. identifier, error, configuration, serialization, record, and telemetry contracts are explicit;
3. Runtime Record reservation and disk-failure behavior are explicit;
4. the old checklist no longer acts as a second architecture source;
5. deferred choices remain unresolved;
6. the project lead performs the final merge.

P0 continues after P0-D5. P1 remains blocked.
