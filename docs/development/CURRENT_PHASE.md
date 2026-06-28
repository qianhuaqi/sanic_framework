# Current Phase

Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Current phase: P0-D7 - Public Governance, Release Policy, and Final Freeze Candidate
Phase type: non-implementation architecture and governance
Accepted baseline: latest accepted `main`
Active decision branch: `human/dodo/phase-p0-d7-governance-freeze`
Active decision Issue: #49
Parent architecture Issue: #25
Status: proposed final P0 decision under project-lead review
Next phase allowed: no

## Completed technical decisions

- P0-D1: repository and concurrent-development governance — ADR-001 / PR #32.
- P0-D2: runtime concurrency — ADR-002 / PR #35.
- P0-D3: package and component layout — ADR-003 / PR #38.
- P0-D4: Application Kernel and request pipeline — ADR-004 / PR #41.
- P0-D5: Hardening Foundations — ADR-005 / PR #44.
- P0-D6: executable, CLI, support matrix, and build baseline — ADR-006 / PR #47.

## Active proposal: P0-D7

P0-D7 proposes:

```text
License:           Apache-2.0
Contribution:      DCO 1.1, Signed-off-by, no initial CLA
Conduct:           Contributor Covenant 2.1 adaptation
Security:          private vulnerability reporting and supported-version rules
Versioning:        SemVer 2.0.0 with stricter 0.x compatibility
First P1 version:  0.1.0.dev0
Branch model:      main only as long-lived branch
Release:           tag-driven CI artifacts, immutable releases, trusted publication
P1:                single-Worker minimum vertical slice
```

Files added by the proposal:

- `LICENSE`;
- `NOTICE`;
- `DCO`;
- `CONTRIBUTING.md`;
- `SECURITY.md`;
- `CODE_OF_CONDUCT.md`;
- `CHANGELOG.md`;
- `docs/governance/RELEASE_AND_COMPATIBILITY_POLICY.md`;
- `docs/development/P1_IMPLEMENTATION_PLAN.md`;
- `docs/decisions/ADR-007-public-governance-release-and-p0-freeze.md`.

## Proposed compatibility rules

Before 1.0:

- patch releases remain compatible inside one minor line;
- breaking public changes require a new minor release;
- breaking changes require changelog and migration guidance;
- removal should normally follow at least one released minor of deprecation.

After 1.0:

- breaking changes require a major release;
- normal removal requires two minor releases and 180 days of deprecation;
- security/data-corruption/protocol emergencies may use a documented narrow exception.

## Proposed P1 scope

P1 is limited to an installable single-Worker vertical slice:

```text
package/CI foundation
→ core identifiers/time/errors/config
→ runtime Scope/Deadline/cancellation/admission
→ HTTP Request/Response/body
→ Router/Middleware
→ Application Kernel/freeze
→ minimum Runtime Record
→ native single-Worker HTTP/1.1 Server
→ CLI version/check/run --workers 1
→ clean wheel/sdist verification
```

Multi-Worker Supervisor, reload, advanced streaming/body formats, official extensions, and public package-index release remain outside P1.

## Freeze gate

Merging the P0-D7 decision PR will create a P0 Freeze Candidate only.

P1 remains blocked until a separate Final Freeze PR:

1. marks ADR-007 Accepted;
2. marks the Blueprint Frozen;
3. closes parent Issue #25;
4. records the final P0 commit;
5. changes the phase to P1 authorized;
6. explicitly authorizes creation of production package files and P1 Issues.

## Current objective

- review License, DCO, conduct, and security policies;
- review 0.x/1.x compatibility and release rules;
- review P1 scope, dependency graph, write scopes, and acceptance matrix;
- verify governance files do not conflict;
- open a documentation/governance Pull Request;
- keep production implementation blocked.

## Prohibited until Final Freeze

- creating `pyproject.toml`, `lingshu/`, `tests/`, examples, or CI workflows;
- adding runtime/build dependencies to the actual project;
- implementing framework code;
- opening executable P1 implementation Issues;
- publishing artifacts.
