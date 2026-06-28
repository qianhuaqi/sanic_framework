# Development Handoff

Updated at: 2026-06-28
Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Phase on merge: P1 - Single-Worker Minimum Vertical Slice
Authorization: project-lead merge of PR #51
Authoritative P0 freeze commit: PR #51 merge commit
P0 parent Issue: #25 (closed by PR #51)
P0 final decision Issue: #49 (closed by PR #51)
First implementation Issue: P1-00, created only after PR #51 merges
Planned version: `0.1.0.dev0`

## Frozen P0 decisions

- ADR-001: repository and concurrent-development governance.
- ADR-002: runtime concurrency, bounded resources, Deadline, cancellation, restart, and shutdown.
- ADR-003: one distribution/import package, root `lingshu/`, no `src/`, component dependency boundaries.
- ADR-004: Application Kernel, immutable Revision/Plan, Router/Middleware/Handler/Request/Response pipeline.
- ADR-005: identifiers, errors, configuration, serialization, Runtime Record, telemetry, redaction, and recovery.
- ADR-006: public single-Worker Server, CLI discovery, multi-Worker design, Python/platform support, Hatchling, version, artifacts, and CI matrix.
- ADR-007: Apache-2.0, DCO, conduct/security governance, SemVer/compatibility, release policy, P1 scope, and final freeze.

Authoritative entry points:

```text
docs/architecture/LINGSHU_FRAMEWORK_BLUEPRINT.md
docs/architecture/P0_FINAL_FREEZE.md
docs/architecture/P0_DECISION_STATUS.md
docs/development/P1_IMPLEMENTATION_PLAN.md
docs/governance/RELEASE_AND_COMPATIBILITY_POLICY.md
```

## Governance baseline

```text
License:        Apache-2.0
Contribution:   DCO 1.1 + Signed-off-by
CLA:            none initially
Code of Conduct: LingShu adaptation of Contributor Covenant 2.1
Security:       private vulnerability reporting
Versioning:     SemVer 2.0.0 with stricter 0.x compatibility
Long-lived branch: main only
Auto-merge:     prohibited
Final merge:    project lead
```

Released versions, tags, and artifacts are immutable. Public package-index publication requires separate project-lead authorization, short-lived trusted identity where available, and retained hashes/provenance.

## P1 outcome

P1 must deliver an installable single-Worker vertical slice:

```python
from lingshu import LingShu, Request, Response

app = LingShu()

@app.get("/")
async def index(request: Request) -> Response:
    return Response.text("hello")
```

```text
lingshu check example:app
lingshu run example:app --workers 1
```

The end-to-end path must preserve RequestId, Runtime Record, absolute Deadline, cancellation, cleanup, bounded resources, safe errors, and package boundaries.

## P1 Issue graph

```text
P1-00 package/tooling/CI foundation
P1-01 core time/identifiers/errors
P1-02 static configuration
P1-03 runtime Scope/Deadline/cancellation/tasks/admission
P1-04 HTTP Request/Response/body model
P1-05 Router/Middleware
P1-06 Application Kernel/Revision/freeze/lifecycle
P1-07 minimum Runtime Record
P1-08 native single-Worker HTTP/1.1 Server
P1-09 CLI version/check/run --workers 1
P1-10 integration/security/packaging/docs
```

Provider contracts merge before consumers. Only the limited parallel waves declared in `P1_IMPLEMENTATION_PLAN.md` are allowed.

## Immediate next action after PR #51 merges

Create P1-00 only.

P1-00 write scope includes:

```text
pyproject.toml
lingshu/__init__.py
lingshu/__main__.py
initial component package markers
initial tests/package harness
.github/workflows/
tooling configuration
README setup section
```

P1-00 requirements:

- base commit is the PR #51 merge commit;
- development version `0.1.0.dev0`;
- root package `lingshu/`, never `src/lingshu/`;
- Hatchling and PEP 621;
- Apache-2.0 package metadata;
- root export placeholder contract;
- DCO/license/package-inventory checks;
- clean non-editable install outside checkout;
- no implementation assigned to P1-01 or later.

## P1 exclusions

- public PyPI production release;
- production-readiness claims;
- multi-Worker Supervisor and listener-transfer implementation;
- development reload and production configuration rollout;
- advanced streaming, multipart, upload, compression, or content encodings;
- HTTP/2, HTTP/3, WebSocket, ASGI, or WSGI;
- automatic HEAD/OPTIONS, host routing, reverse routing, mounts, or sub-applications;
- sync Handler adaptation or dependency injection;
- official Auth, Tenant, RBAC, SQL, Redis, Cache, OpenAPI, Scheduler, Storage, or Observability integrations;
- changes to frozen architecture without a new Issue and ADR.

## Handoff verification

- no production package, test skeleton, root `pyproject.toml`, implementation workflow, or runtime dependency was added before Final Freeze;
- no executable P1 Issue was opened before Final Freeze;
- PR #51 body closes Issue #49 and #25 when merged;
- PR #51 merge is the only explicit P1 authorization event;
- archive branch `archive/legacy-sanic-20260628` remains preserved.
