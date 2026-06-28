# Development Handoff

Updated at: 2026-06-28
Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Phase: P0-D3 - Package, Source Layout, and Component Boundaries
Parent Issue: #25
Active decision Issue: #37
Active decision branch: `human/dodo/phase-p0-d3-package-layout`
Baseline: latest accepted `main`
Status: proposed architecture ready for review

## Previous accepted decisions

### P0-D1

Single repository and development concurrency governance are accepted through ADR-001 and PR #32.

### P0-D2

Runtime concurrency is accepted through ADR-002 and PR #35.

## Project-lead direction for P0-D3

多多明确不采用 `src/` 目录。

## P0-D3 proposal completed on this branch

- Added `ADR-003-package-source-layout-and-component-boundaries.md`.
- Added `PACKAGE_AND_COMPONENT_LAYOUT.md`.
- Proposed one distribution named `lingshu`.
- Proposed one import package named `lingshu`.
- Proposed one root-level `pyproject.toml`.
- Proposed root-level production source at `lingshu/`.
- Explicitly rejected `src/lingshu/` and `packages/` for the initial framework.
- Proposed internal components: `core`, `runtime`, `http`, `server`, `record`, `extensions`, `cli`, and `testing`.
- Defined responsibilities and allowed/forbidden dependencies for each component.
- Proposed Runtime Record mechanisms as part of the default distribution.
- Defined controlled public exports and private deep imports.
- Defined lazy optional dependency behavior.
- Defined root directories for tests, docs, examples, tools, benchmarks, and fuzzing.
- Defined mandatory wheel/sdist build and clean-install tests outside the repository checkout.
- Kept all work documentation-only; no package skeleton or production code was created.

## Proposed target tree

```text
.
├─ lingshu/
│  ├─ core/
│  ├─ runtime/
│  ├─ http/
│  ├─ server/
│  ├─ record/
│  ├─ extensions/
│  ├─ cli/
│  └─ testing/
├─ tests/
├─ docs/
├─ examples/
├─ tools/
├─ benchmarks/
├─ fuzz/
└─ pyproject.toml
```

This tree is not created during P0.

## Dependency proposal

```text
runtime     → core
http        → runtime + core
server      → http + runtime + core
record      → core + stable runtime contracts
extensions  → core + runtime (+ documented HTTP contracts when needed)
cli         → public composition surface
testing     → public/test-support surfaces
```

Production components must never depend on `testing`. Lower components must not import the root facade or higher components.

## Intentionally deferred

- minimum Python version;
- build backend;
- exact public class and function names;
- authoritative version-file mechanism;
- optional dependency extras;
- official extension implementations;
- first PyPI release timing;
- post-v1.0 compatibility policy.

## Verification

This branch contains architecture and governance documentation only. It adds no production source, package directory, `pyproject.toml`, runtime dependency, implementation, or publishing configuration.

Review must verify:

- `src/` remains rejected;
- only one initial distribution and one version are proposed;
- dependency cycles are prohibited;
- Runtime Record is built in without forcing heavy storage integrations;
- optional integrations remain lazy;
- wheel isolation tests prevent checkout imports from masking packaging defects;
- P1 remains blocked.

## Next action

Review and merge the P0-D3 decision Pull Request only if the package and component architecture is accepted. Do not create the production tree or start P1.
