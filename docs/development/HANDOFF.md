# Development Handoff

Updated at: 2026-06-28
Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Phase: P0 - Architecture Decision Review and Blueprint Consolidation
Parent Issue: #25
Active decision Issue: none
Active decision branch: none
Baseline: latest accepted `main`
Status: P0-D3 accepted; awaiting P0-D4

## Accepted decisions

### P0-D1

Single repository and development concurrency governance are accepted through ADR-001 and PR #32.

### P0-D2

Runtime concurrency is accepted through ADR-002 and PR #35.

### P0-D3

Package, source layout, and component boundaries are accepted through ADR-003 and PR #38.

- Issue #37 completed.
- Merge commit: `66c977f435c23fc9aaa35c4f085a7ca20a81879a`.
- Detailed model: `docs/architecture/PACKAGE_AND_COMPONENT_LAYOUT.md`.

Confirmed layout:

```text
Repository:      qianhuaqi/lingshu
Distribution:    lingshu
Import package:  lingshu
Packaging file:  pyproject.toml
Production code: lingshu/
src layout:      prohibited
```

Confirmed target components:

```text
lingshu.core
lingshu.runtime
lingshu.http
lingshu.server
lingshu.record
lingshu.extensions
lingshu.cli
lingshu.testing
```

Confirmed dependency direction:

```text
runtime     → core
http        → runtime + core
server      → http + runtime + core
record      → core + stable runtime contracts
extensions  → core + runtime (+ documented HTTP contracts when required)
cli         → public composition surface
testing     → public/test-support surfaces
```

Additional confirmed rules:

- one framework version and release cadence;
- no initial multiple distributions or component-level `pyproject.toml` files;
- no dependency cycles;
- production components do not import `testing`;
- `lingshu/__init__.py` is the controlled public facade;
- deep imports are private unless explicitly documented;
- optional integrations load lazily and remain non-mandatory;
- Runtime Record mechanisms ship by default while heavy exporters remain optional;
- package validation builds wheel and sdist, installs into a clean environment, and tests from outside the checkout without repository `PYTHONPATH` injection.

## Intentionally deferred

- minimum Python version and platform matrix;
- build backend;
- exact public application/request/response and runtime API names;
- API manifest mechanism;
- authoritative version-source mechanism;
- optional extras and official integrations;
- first PyPI release timing;
- post-v1.0 compatibility policy.

## Next decision

P0-D4 should define:

- Application Kernel and composition responsibilities;
- application lifecycle and freeze boundaries;
- route registration and compilation;
- request execution pipeline and stage order;
- middleware scopes and ordering;
- Request and Response ownership/mutability;
- exception mapping and response commit semantics;
- minimal public API and root exports;
- extension participation in application startup and request handling.

## Verification

P0-D3 added architecture and governance documentation only. No production source directory, `pyproject.toml`, runtime dependency, framework implementation, or publishing configuration was created.

P1 remains blocked.
