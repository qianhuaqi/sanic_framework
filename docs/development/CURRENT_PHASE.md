# Current Phase

Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Current phase: P0 - Architecture Decision Review and Blueprint Consolidation
Phase type: non-implementation architecture and governance
Accepted baseline: latest accepted `main`
Active decision branch: none
Active decision Issue: none
Parent architecture Issue: #25
Status: awaiting the next project-lead architecture decision
Next phase allowed: no

## Foundational fact

LingShu is a completely new, independently implemented Python Web/API framework.

It does not depend on Sanic, FastAPI, Flask, Django, Starlette, or any other upper-level Web framework. The archived implementation creates no compatibility obligation.

The previous implementation is preserved at `archive/legacy-sanic-20260628` and is not an active source of truth.

## Completed decisions

### P0-D1: Single repository and concurrency governance

Implemented by PR #32 and ADR-001.

Confirmed:

- one canonical GitHub repository: `qianhuaqi/lingshu`;
- no separate repositories for Core, HTTP, Server, Record, or official capabilities during initial development;
- one Issue, writer-prefixed branch, primary writer, independent worktree or clone, virtual environment, and Pull Request per concurrent task;
- explicit write scopes, dependencies, conflicts, integration order, and required checks;
- independent tasks may run in parallel;
- overlapping paths and shared contracts are serialized;
- provider contracts merge before dependent work;
- development may be parallel, but integration into `main` is serial;
- runtime concurrency must be bounded, isolated, cancellable, observable, backpressured, and deterministically cleaned up.

## Still unresolved

The following remain candidates and must not be implemented yet:

- one Python distribution versus multiple distributions inside the single repository;
- `packages/` versus another repository layout;
- direct `lingshu/` versus a `src/` layout;
- exact Core, HTTP, Server, Record, CLI, testing, and extension boundaries;
- runtime event-loop, worker, process, thread, task-group, admission-control, and shutdown models;
- built-in versus separately installable capabilities;
- release-version mapping and compatibility policy;
- supported Python and platform range;
- license and public contribution/security policies.

## Current objective

1. Select the next unresolved architecture decision under Issue #25.
2. Create a dedicated decision Issue with explicit scope and exclusions.
3. Update the Blueprint and decision-status register only after project-lead confirmation.
4. Keep P1 blocked until all P0 exit conditions are satisfied.

## Out of scope

- Production framework implementation.
- Source package or directory skeleton creation.
- Runtime dependency introduction.
- Package publication.
- Starting P1.

## P0 exit conditions

P0 ends only when:

1. the project lead confirms the complete Blueprint;
2. all accepted hardening items are integrated into that single Blueprint;
3. package, source, component, dependency, extension, and runtime-concurrency structures are explicitly confirmed;
4. release stages and P1 acceptance criteria are ready;
5. all legacy implementation Issues are closed or historical;
6. governance files are internally consistent;
7. the project lead explicitly authorizes creation of the P1 Issue.

P1 remains blocked.
