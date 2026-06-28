# Current Phase

Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Current phase: P0-D3 - Package, Source Layout, and Component Boundaries
Phase type: non-implementation architecture and governance
Accepted baseline: latest accepted `main`
Active decision branch: `human/dodo/phase-p0-d3-package-layout`
Active decision Issue: #37
Parent architecture Issue: #25
Status: proposed architecture under project-lead review
Next phase allowed: no

## Foundational fact

LingShu is a completely new, independently implemented Python Web/API framework.

It does not depend on Sanic, FastAPI, Flask, Django, Starlette, or another upper-level Web framework. The archived implementation creates no compatibility obligation.

## Completed decisions

### P0-D1: Single repository and development concurrency

Accepted through ADR-001 and PR #32.

### P0-D2: Runtime concurrency

Accepted through ADR-002 and PR #35.

The accepted runtime uses standard-library `asyncio` semantics, one event loop per Worker, structured task ownership, bounded admission and backpressure, absolute monotonic Deadline propagation, explicit cancellation, bounded blocking-work isolation, and ordered graceful shutdown.

## Active decision proposal

### P0-D3: Package and component layout

The project lead has rejected adding a `src/` directory.

The proposal defines:

- one Python distribution: `lingshu`;
- one import package: `lingshu`;
- one root `pyproject.toml`;
- production source directly under root-level `lingshu/`;
- no `src/` and no `packages/` layout;
- internal components: `core`, `runtime`, `http`, `server`, `record`, `extensions`, `cli`, and `testing`;
- one shared framework version and release cadence;
- default inclusion of Runtime Record mechanisms;
- explicit dependency direction and cycle prohibition;
- controlled root public facade and explicit exports;
- optional integrations loaded lazily without becoming core dependencies;
- root-level tests, docs, examples, tools, benchmarks, and fuzz directories;
- mandatory wheel/sdist clean-install tests outside the repository checkout.

Detailed proposal:

- `docs/decisions/ADR-003-package-source-layout-and-component-boundaries.md`
- `docs/architecture/PACKAGE_AND_COMPONENT_LAYOUT.md`

## Explicitly unresolved

P0-D3 does not decide:

- minimum Python version;
- build backend;
- exact public application, request, response, Scope, Deadline, limiter, or cancellation names;
- exact authoritative version-file mechanism;
- optional dependency extras and official integration catalog;
- first PyPI release timing;
- post-v1.0 compatibility policy.

## Current objective

1. review the single-distribution and root-level package proposal;
2. confirm component responsibilities and dependency direction;
3. confirm the public/private API rules;
4. confirm isolated wheel and sdist quality gates;
5. open a documentation-only Pull Request;
6. keep P1 blocked.

## Out of scope

- creating `lingshu/`, `tests/`, or `pyproject.toml`;
- production framework implementation;
- runtime dependency introduction;
- package publication;
- starting P1.

## Exit conditions for P0-D3

1. ADR-003 and the detailed layout document are reviewed and merged;
2. one distribution, one import package, and one root packaging file are explicit;
3. no-`src` and root-level `lingshu/` are explicit;
4. component boundaries and dependency rules are explicit;
5. public export and optional dependency rules are explicit;
6. clean wheel/sdist installation gates are explicit;
7. deferred decisions remain unresolved;
8. the project lead performs the final merge.

P0 continues after P0-D3. P1 remains blocked.
