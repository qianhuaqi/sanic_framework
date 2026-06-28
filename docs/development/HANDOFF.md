# Development Handoff

Updated at: 2026-06-28
Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Phase: P0-D7 - Public Governance, Release Policy, and Final Freeze Candidate
Parent Issue: #25
Active decision Issue: #49
Active decision branch: `human/dodo/phase-p0-d7-governance-freeze`
Baseline: latest accepted `main`
Status: proposed final P0 decision ready for review

## Accepted technical decisions

- P0-D1: repository/concurrent-development governance — ADR-001 / PR #32.
- P0-D2: runtime concurrency — ADR-002 / PR #35.
- P0-D3: package/component layout — ADR-003 / PR #38.
- P0-D4: Application Kernel/request pipeline — ADR-004 / PR #41.
- P0-D5: Hardening Foundations — ADR-005 / PR #44.
- P0-D6: executable/CLI/support/build baseline — ADR-006 / PR #47.

## P0-D7 proposal

### License and contribution

```text
License: Apache License 2.0
NOTICE: required project/third-party attribution record
DCO: Developer Certificate of Origin 1.1
Commit rule: Signed-off-by on every commit
CLA: not required initially
```

### Conduct and security

- project Code of Conduct adapted from Contributor Covenant 2.1;
- private reporting and conflict-of-interest handling;
- GitHub Private Vulnerability Reporting required before first public release;
- no public disclosure of unpatched exploit details;
- best-effort acknowledgment in 3 business days and triage in 7;
- before 1.0, latest minor line only is supported unless announced otherwise.

### Version and compatibility

```text
SemVer:             2.0.0
First P1 version:   0.1.0.dev0
Tag format:         vX.Y.Z
Long-lived branch:  main only
```

Pre-1.0 patches remain compatible inside their minor line. Breaking changes require a minor bump, migration guidance, and normally one prior minor of deprecation.

After 1.0, breaking changes require a major bump. Normal removal requires at least two minor releases and 180 days of deprecation.

### Release

```text
release PR
→ merge to main
→ annotated tag
→ protected CI build
→ artifact tests/inventory
→ provenance/attestation
→ authorized publication
```

Released versions, tags, and artifacts are immutable. A defective release is yanked or superseded, not overwritten.

Public package-index publication uses short-lived identity-based trusted publishing when available and does not store a long-lived production token in CI.

### P1 minimum vertical slice

P1 planned version: `0.1.0.dev0`.

P1 includes:

- package/CI skeleton with no `src/`;
- core time/identifier/error/config primitives;
- runtime Scope, Deadline, cancellation, task, admission primitives;
- HTTP Request/Response/body foundation;
- Router and Middleware;
- Application Kernel, Revision, freeze, lifecycle;
- minimum Runtime Record;
- native single-Worker HTTP/1.1 Server;
- CLI `version`, `check`, `run --workers 1`;
- wheel/sdist and clean-install gates.

P1 excludes multi-Worker Supervisor, development reload, production config reload, advanced streaming/body formats, official extensions, and public PyPI release.

## Planned P1 Issue graph

```text
P1-00 package/tooling/CI foundation
→ P1-01 core primitives
→ P1-02 configuration
→ P1-03 runtime
→ P1-04 HTTP model
→ P1-05 Router/Middleware
→ P1-06 Application Kernel
→ P1-07 Runtime Record
→ P1-08 single-Worker Server
→ P1-09 CLI
→ P1-10 integration/security/packaging/docs
```

P1-02 and P1-03 may overlap after P1-01. P1-07 may overlap with HTTP work once runtime contracts merge. Provider contracts always merge before consumers.

Detailed graph and acceptance matrix:

- `docs/development/P1_IMPLEMENTATION_PLAN.md`.

## Freeze semantics

The P0-D7 decision PR does not authorize production development.

After it merges, a separate Final Freeze PR must:

- mark ADR-007 Accepted;
- mark Blueprint Frozen;
- verify all ADR/control documents;
- close Issue #49 and parent Issue #25;
- explicitly state P1 authorization;
- permit creation of `pyproject.toml`, `lingshu/`, `tests/`, workflows, and executable P1 Issues.

Only the project lead's merge of Final Freeze ends P0.

## Review checklist

- Apache-2.0 text and NOTICE are correct;
- DCO text is unchanged and CONTRIBUTING requires sign-off;
- security policy has a private reporting path without an invented mailbox;
- supported-version rules agree;
- Code of Conduct has confidential reporting and conflict handling;
- SemVer/0.x/deprecation/release rules agree across files;
- changelog categories are stable;
- P1 plan respects package, ownership, dependency, and scope boundaries;
- no production source, package skeleton, dependency, or workflow was added.

## Next action

Review the P0-D7 governance/freeze-candidate Pull Request. P1 remains blocked.
