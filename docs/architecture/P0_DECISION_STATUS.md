# P0 Architecture Decision Status

- Status: Active P0 control document
- Parent Issue: #25
- Active decision Issue: #49
- Active proposal: P0-D7 / ADR-007
- Last accepted decision: P0-D6 / ADR-006 / PR #47
- Last updated: 2026-06-28

## Authority

`LINGSHU_FRAMEWORK_BLUEPRINT.md` is the single overall architecture document. This file records decision state only.

- **Confirmed** decisions may be used by later implementation Issues.
- **Proposed** and **Candidate** decisions must not be implemented.
- **Rejected** decisions require a new Issue, ADR, and project-lead approval before reconsideration.

## Confirmed decisions

### P0-D1

Repository and concurrent-development governance accepted through ADR-001 / PR #32.

### P0-D2

Runtime concurrency accepted through ADR-002 / PR #35: one event loop/runtime per Worker, structured ownership, bounded resources/backpressure, monotonic Deadline, cancellation propagation, bounded restart, and graceful shutdown.

### P0-D3

Package/component layout accepted through ADR-003 / PR #38:

```text
Distribution:    lingshu
Import package:  lingshu
Production code: lingshu/
src layout:      prohibited
```

### P0-D4

Application Kernel/request pipeline accepted through ADR-004 / PR #41: controlled public facade, immutable revisions/plans, deterministic Router/Middleware, async Handler, Request/Response contracts, irreversible commit, and deterministic exception mapping.

### P0-D5

Hardening Foundations accepted through ADR-005 / PR #44: typed identifiers, time model, safe errors, strict configuration/serialization, Runtime Record reservation/storage/recovery, telemetry redaction, and bounded cardinality.

### P0-D6

Executable/CLI/support/build baseline accepted through ADR-006 / PR #47:

- public single-Worker Server;
- strict CLI target grammar;
- spawn-based multi-Worker semantics;
- one-time listener bind/transfer;
- readiness, signals, and exit codes;
- CPython 3.12 minimum and required matrix;
- Hatchling, PEP 621, static project version, console script;
- pure wheel/sdist and clean-install gates.

## Proposed — P0-D7, not executable until Final Freeze

Issue #49 and ADR-007 propose:

### Public governance

```text
License:      Apache-2.0
Contribution: DCO 1.1 with Signed-off-by
CLA:          none initially
Conduct:      Contributor Covenant 2.1 adaptation
```

Proposed repository files:

```text
LICENSE
NOTICE
DCO
CONTRIBUTING.md
SECURITY.md
CODE_OF_CONDUCT.md
CHANGELOG.md
```

### Security

- private vulnerability reporting before first public release;
- no public disclosure of unpatched exploit details;
- best-effort response targets;
- latest `0.y` minor supported before 1.0 unless otherwise announced;
- current major latest minor supported after 1.0, with a normal 180-day previous-major transition for critical/high fixes.

### Version and compatibility

```text
SemVer:           2.0.0
First P1 version: 0.1.0.dev0
Tags:             vX.Y.Z and prerelease forms
Long-lived branch: main only
```

- pre-1.0 patches compatible inside one minor line;
- pre-1.0 breaking changes require a minor bump, migration guidance, and normally one prior minor of deprecation;
- post-1.0 breaking changes require a major bump;
- normal post-1.0 removal requires two minor releases and 180 days of deprecation;
- security/corruption/protocol emergencies may use narrow documented exceptions;
- released versions, tags, and artifacts remain immutable.

### Release

- release PR updates version/changelog and passes full gates;
- annotated tag triggers protected CI build;
- authoritative artifacts come from tag CI;
- tag, metadata, changelog, and release notes agree;
- public package publication uses short-lived trusted identity where available;
- artifact hashes and provenance/attestation are retained;
- defective releases are yanked/superseded rather than overwritten.

### P1 plan

P1 is a single-Worker minimum vertical slice with planned version `0.1.0.dev0`.

Included:

- package/tooling/CI foundation;
- core time, identifiers, errors, static configuration;
- runtime Scope, Deadline, cancellation, tasks, admission;
- HTTP model/body/response commit;
- Router/Middleware;
- Application Kernel/freeze/lifecycle;
- minimum Runtime Record;
- native single-Worker HTTP/1.1 Server;
- CLI `version`, `check`, and `run --workers 1`;
- clean wheel/sdist acceptance.

Excluded:

- multi-Worker Supervisor;
- file reload and production configuration rollout;
- advanced streaming/body formats;
- official extensions;
- public package-index production release.

Detailed graph: `docs/development/P1_IMPLEMENTATION_PLAN.md`.

### Freeze gate

Merging the P0-D7 decision PR creates a Freeze Candidate only. It does not authorize production code.

A separate Final Freeze PR must:

1. mark ADR-007 Accepted;
2. mark Blueprint Frozen;
3. verify ADR-001 through ADR-007 consistency;
4. close Issue #49 and parent Issue #25;
5. record the final P0 commit;
6. set phase to P1 authorized;
7. explicitly permit production package files and executable P1 Issues.

Only the project lead's merge of Final Freeze ends P0.

Proposal documents:

- `docs/decisions/ADR-007-public-governance-release-and-p0-freeze.md`;
- `docs/governance/RELEASE_AND_COMPATIBILITY_POLICY.md`;
- `docs/development/P1_IMPLEMENTATION_PLAN.md`.

## Rejected principles

Previously rejected principles remain rejected. P0-D7 additionally rejects:

- missing or placeholder license metadata;
- initial non-open-source licensing;
- initial CLA requirement instead of DCO;
- unsigned contributions;
- public vulnerability Issues as the primary channel;
- undocumented arbitrary breaking patch releases during 0.x;
- modifying released artifacts in place;
- long-lived `develop`;
- workstation-built authoritative release artifacts;
- long-lived production package-index credentials in CI;
- automatic P1 start after proposal merge;
- broad P1 implementation before the single-Worker vertical slice.

## Candidate — deferred after P0

- exact numeric defaults and health endpoint paths;
- multi-Worker Supervisor and listener transfer implementation;
- development reload and production configuration rollout;
- advanced routing, streaming, multipart, uploads, compression;
- sync Handler adaptation and dependency injection;
- official capabilities/extensions;
- HTTP/2, HTTP/3, WebSocket, ASGI/WSGI;
- extra runtimes/platforms and native extensions;
- public package-index release date and manual signing scheme;
- trademark and long-term-support governance.

## Confirmation rule

P0-D7 becomes Confirmed only after the decision PR is reviewed/merged and the dedicated Final Freeze PR is merged by the project lead.

P1 remains blocked until Final Freeze.
