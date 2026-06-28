# Current Phase

Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Current phase: P1 - Single-Worker Minimum Vertical Slice
Authorization event: project-lead merge of PR #51
Authoritative P0 freeze commit: merge commit of PR #51
Phase status on `main`: P1 Authorized
Active implementation Issue: none until PR #51 merges
First authorized Issue: P1-00
P1 planned version: `0.1.0.dev0`
Parent P0 Issue: #25 (closed by PR #51)
Final P0 decision Issue: #49 (closed by PR #51)

> This phase transition is effective only when PR #51 reaches `main`. While PR #51 remains open, production work and executable P1 Issues remain blocked.

## P0 result

P0 is frozen through:

```text
ADR-001  repository and concurrent-development governance
ADR-002  runtime concurrency and graceful shutdown
ADR-003  package/source/component boundaries
ADR-004  Application Kernel and request pipeline
ADR-005  hardening foundations
ADR-006  executable/CLI/support/build baseline
ADR-007  public governance, compatibility, release, and P0 freeze
```

Authoritative documents:

- `docs/architecture/LINGSHU_FRAMEWORK_BLUEPRINT.md`;
- `docs/architecture/P0_FINAL_FREEZE.md`;
- `docs/architecture/P0_DECISION_STATUS.md`;
- accepted ADRs;
- `docs/governance/RELEASE_AND_COMPATIBILITY_POLICY.md`;
- `docs/development/P1_IMPLEMENTATION_PLAN.md`.

## P1 objective

Build the first independently implemented, installable, tested LingShu vertical slice:

```text
package + CI
→ core primitives
→ runtime scopes
→ HTTP model
→ Router/Middleware
→ Application Kernel
→ minimum Runtime Record
→ single-Worker HTTP/1.1 Server
→ CLI version/check/run --workers 1
→ clean wheel/sdist verification
```

P1 is an implementation proof of the frozen architecture. It is not a public stable release and does not authorize production-readiness claims.

## First authorized action

After PR #51 merges, create only:

```text
P1-00：建立 package、tooling、CI 与治理门禁基础
```

P1-00 must:

- use the PR #51 merge commit as `base_commit`;
- use one writer-prefixed branch, one primary writer, one isolated environment, and one PR;
- create `pyproject.toml`, the initial no-`src/` `lingshu/` package skeleton, initial `tests/` harness, tooling configuration, and CI workflows only inside its declared scope;
- set the development version to `0.1.0.dev0`;
- use Hatchling, PEP 621, Apache-2.0 metadata, and the accepted console-entry baseline;
- establish package inventory and clean-install gates;
- avoid implementing framework behavior assigned to P1-01 and later.

## P1 dependency order

```text
P1-00 package/tooling/CI
→ P1-01 core primitives
→ P1-02 static configuration
→ P1-03 runtime
→ P1-04 HTTP model
→ P1-05 Router/Middleware
→ P1-06 Application Kernel
→ P1-07 Runtime Record
→ P1-08 single-Worker Server
→ P1-09 CLI
→ P1-10 final integration
```

Limited parallel work is allowed only where `P1_IMPLEMENTATION_PLAN.md` explicitly permits it and consumed provider contracts are already merged.

## P1 scope

Authorized:

- package/tooling/CI foundation;
- core time, identifiers, errors, safe details, and static configuration;
- Scope, Deadline, cancellation, structured tasks, cleanup, and admission;
- HTTP Request, Response, body, Router, and Middleware foundations;
- Application Kernel, Revision, freeze, and lifecycle;
- minimum Runtime Record;
- native single-Worker HTTP/1.1 Server;
- CLI `version`, `check`, and `run --workers 1`;
- wheel/sdist and outside-checkout clean-install verification.

Not authorized in P1:

- public PyPI production publication;
- multi-Worker Supervisor implementation;
- development or production reload;
- HTTP/2, HTTP/3, WebSocket, ASGI, or WSGI;
- advanced streaming, multipart, uploads, or compression;
- automatic HEAD/OPTIONS, host routing, mounts, or sub-applications;
- sync Handler adaptation or dependency injection;
- official Auth, Tenant, RBAC, SQL, Redis, Cache, OpenAPI, Scheduler, Storage, or Observability integrations;
- changing frozen P0 decisions without a new Issue and ADR.

## Governance remains active

- one task = one Issue = one primary writer = one branch/worktree/environment = one PR;
- no direct commit to `main`;
- no shared writable workspace or multi-writer branch;
- no long-lived `develop`;
- no auto-merge;
- DCO sign-off required;
- final merge authority belongs to the project lead.
