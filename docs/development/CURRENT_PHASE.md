# Current Phase

Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Current phase: P0 - Architecture Decision Review and Blueprint Consolidation
Phase type: non-implementation architecture and governance
Accepted baseline: latest accepted `main`
Active decision branch: none
Active decision Issue: none
Parent architecture Issue: #25
Status: P0-D6 accepted; awaiting final governance and freeze decision
Next phase allowed: no

## Foundational fact

LingShu is a new, independently implemented Python Web/API framework. It does not depend on Sanic, FastAPI, Flask, Django, Starlette, or another upper-level Web framework.

## Completed decisions

- P0-D1: repository and concurrent-development governance — ADR-001 / PR #32.
- P0-D2: runtime concurrency — ADR-002 / PR #35.
- P0-D3: package and component layout — ADR-003 / PR #38.
- P0-D4: Application Kernel and request pipeline — ADR-004 / PR #41.
- P0-D5: Hardening Foundations — ADR-005 / PR #44.
- P0-D6: executable, CLI, support matrix, and build baseline — ADR-006 / PR #47.

P0-D6 effective merge commit:

```text
5f89572398cee509b9571ee1fe8c20bd2f71dfeb
```

## Confirmed P0-D6 baseline

### Public execution

```python
from lingshu.server import Server, ServerConfig, serve
```

`Server` and `serve` are single-Worker. Multi-Worker Supervisor remains CLI/internal initially. Application does not supervise processes and Kernel does not import Server.

### CLI

```text
lingshu run module:app
lingshu run module:create_app --factory
lingshu check module:app
lingshu version
python -m lingshu ...
```

Discovery accepts strict `module:attribute` only. No expressions, file paths, calls, implicit scanning, or dotted attribute traversal.

### Processes and shutdown

- multi-Worker semantics use cross-platform `spawn`;
- each Worker independently imports/freezes its Application and reports RevisionId;
- Supervisor binds listeners once and explicitly transfers them;
- readiness requires identical RevisionId and all required resources/record policy;
- first termination drains, second or timeout hard-stops;
- stable exit codes 0, 1, 2, 3, 4, 5, 6, 7, 8, and 70.

### Support and build

```text
CPython minimum: 3.12
Required:        3.12, 3.13, 3.14
Preview:         3.15 prerelease
Platforms:       Tier 1 64-bit Linux, Windows, macOS
Build backend:   Hatchling
Version source:  [project].version
Console script:  lingshu = "lingshu.cli:main"
Artifacts:       py3-none-any wheel + sdist
```

Packaging acceptance requires isolated build, inventory inspection, non-editable clean install outside checkout, sdist rebuild, separate editable testing, and uninstall verification.

## Still unresolved

- License selection and metadata;
- contribution, code-of-conduct, and contributor-certificate/DCO policy;
- security disclosure, supported security versions, and vulnerability handling;
- changelog and release-note policy;
- SemVer/pre-1.0 compatibility and deprecation policy;
- release branches/tags, first development version, PyPI timing, signing, and attestations;
- exact numeric defaults and health endpoint paths;
- P1 implementation scope, dependency ordering, Issue breakdown, and acceptance matrix;
- final P0 Blueprint freeze and explicit P1 authorization.

## Recommended next decision

P0-D7 should be the final P0 governance and freeze decision:

1. choose License and required repository governance files;
2. define contribution and code-of-conduct rules;
3. define security reporting and supported-version policy;
4. define changelog, release notes, SemVer/pre-1.0 compatibility, deprecation, and removal rules;
5. define tags, branches, version bump, artifact publication, signing/attestation, and rollback policy;
6. define the first development version and P1 milestone mapping;
7. create an executable P1 Issue graph and acceptance matrix;
8. perform the final Blueprint consistency audit;
9. explicitly freeze P0 and authorize or withhold P1.

## Out of scope

- creating production package files, code, tests, or workflows;
- adding dependencies;
- publishing artifacts;
- beginning P1 before explicit authorization.

P1 remains blocked.
