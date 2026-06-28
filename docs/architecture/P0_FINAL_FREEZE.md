# LingShu P0 Final Freeze Record

- Status: Effective when PR #51 is merged to `main`
- Final Freeze Pull Request: #51
- Freeze candidate source: PR #50
- P0 decision Issue: #49
- Parent architecture Issue: #25
- Project lead: 多多
- Canonical repository: `qianhuaqi/lingshu`

## Authorization event

The project lead's merge of PR #51 is the sole P0 completion and P1 authorization event.

The merge commit of PR #51 is the authoritative final P0 commit. No earlier branch commit, approval, comment, or Freeze Candidate authorizes implementation.

## Frozen decision set

The following decisions are accepted and frozen as the P1 implementation baseline when PR #51 merges:

```text
ADR-001  repository and concurrent-development governance
ADR-002  runtime concurrency and graceful shutdown
ADR-003  package/source/component boundaries
ADR-004  Application Kernel and request pipeline
ADR-005  hardening foundations
ADR-006  executable/CLI/support/build baseline
ADR-007  public governance, compatibility, release, and P0 freeze
```

A change to a frozen decision requires a dedicated Issue and a new ADR that explicitly supersedes or amends the accepted decision. Implementation work cannot silently reinterpret P0.

## Final consistency audit

### Architecture authority

- [x] `LINGSHU_FRAMEWORK_BLUEPRINT.md` is the only overall architecture entry point.
- [x] ADR-001 through ADR-007 have no contradictory active proposal.
- [x] `P0_DECISION_STATUS.md`, `CURRENT_PHASE.md`, and `HANDOFF.md` point to the same accepted baseline on this branch.
- [x] the archived legacy branch remains historical reference only.

### Package and dependency boundary

- [x] one repository, one distribution, one import package, one version cadence.
- [x] production code is rooted at `lingshu/`; `src/lingshu/` is prohibited.
- [x] the root public facade remains controlled.
- [x] component dependency direction is acyclic and machine-verifiable.
- [x] no mandatory runtime dependency is introduced without a separate review.

### Runtime and HTTP contracts

- [x] one event loop and Application Runtime per Worker.
- [x] structured task ownership, bounded resources, backpressure, Deadline, cancellation, and cleanup are required.
- [x] Application freeze publishes one immutable Plan.
- [x] Request/Response/Router/Middleware/Handler/commit contracts are explicit.
- [x] Runtime Record reservation and bounded storage/recovery are required.
- [x] the P1 server scope is one Worker and the accepted HTTP/1.1 subset.

### Executable and build contracts

- [x] public `Server`, `ServerConfig`, and `serve` are single-Worker.
- [x] CLI target grammar is strict `module:attribute`.
- [x] CPython 3.12 is the minimum and accepted compatibility matrix is documented.
- [x] Hatchling, PEP 621, static `[project].version`, console script, wheel/sdist, and clean-install gates are accepted.
- [x] multi-Worker and reload semantics are designed but their implementation is deferred beyond P1.

### Governance

- [x] Apache License 2.0, NOTICE, and DCO 1.1 are present.
- [x] contributions require `Signed-off-by`; no initial CLA is required.
- [x] contribution, conduct, private security reporting, changelog, compatibility, and release policies exist.
- [x] released versions and artifacts are immutable.
- [x] public package publication requires separate authorization and trusted short-lived credentials where available.

### P1 readiness

- [x] planned version is `0.1.0.dev0`.
- [x] P1 is a single-Worker minimum vertical slice.
- [x] P1-00 through P1-10 have provider-first dependencies, write-scope guidance, parallel waves, and acceptance criteria.
- [x] multi-Worker Supervisor, reload, advanced protocols/body formats, official integrations, and public publication are excluded.
- [x] P1 implementation starts with P1-00 only after PR #51 merges.

### Repository state before authorization

- [x] no production `lingshu/` package exists.
- [x] no production `tests/` skeleton exists.
- [x] no root `pyproject.toml` exists.
- [x] no implementation CI workflow exists.
- [x] no executable P1 implementation Issue has been opened.

## Effect of merge

When PR #51 reaches `main`:

1. P0 is complete and frozen.
2. ADR-007 is Accepted.
3. Issue #49 and parent Issue #25 are completed by the PR close directives.
4. P1 is authorized.
5. The team may create P1-00 through P1-10 Issues in dependency order.
6. P1-00 may create `pyproject.toml`, the initial `lingshu/` and `tests/` skeletons, tooling configuration, and CI workflows within its declared write scope.
7. No later P1 Issue may begin before its provider dependencies merge.
8. Final merge authority and no-auto-merge rules remain active.

## First authorized action

After merge, create only P1-00 first:

```text
P1-00：建立 package、tooling、CI 与治理门禁基础
```

P1-00 must be based on the PR #51 merge commit and must not implement framework behavior beyond the accepted package/tooling foundation.

## Not authorized by this freeze

- public PyPI publication;
- production-readiness claims;
- multi-Worker Supervisor implementation;
- development or production reload implementation;
- HTTP/2, HTTP/3, WebSocket, ASGI, or WSGI;
- advanced streaming, multipart, uploads, or compression;
- official Auth, Tenant, RBAC, SQL, Redis, Cache, OpenAPI, Scheduler, Storage, or Observability integrations;
- changes to the frozen architecture without a new Issue and ADR.
