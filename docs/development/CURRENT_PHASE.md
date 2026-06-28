# Current Phase

Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Current phase: P0-D1 - Single Repository and Concurrency Governance
Phase type: non-implementation architecture and governance
Current baseline: latest accepted `main`
Active branch: `human/dodo/phase-p0-d1-single-repo-concurrency`
Current Issue: #31
Parent architecture Issue: #25
Status: decision documentation and review
Next phase allowed: no

## Foundational fact

LingShu is a completely new, independently implemented Python Web/API framework.

It does not depend on Sanic, FastAPI, Flask, Django, Starlette, or any other upper-level Web framework. The archived implementation creates no compatibility obligation.

The previous implementation is preserved at `archive/legacy-sanic-20260628` and is not an active source of truth.

## Confirmed in this decision

- LingShu uses one canonical GitHub repository: `qianhuaqi/lingshu`.
- Core, official capabilities, tests, documentation, tooling, and release metadata are governed in this repository unless a future ADR proves a separate repository is necessary.
- Single repository does not mean a shared branch or shared writable directory.
- Concurrent tasks use independent Issues, branches, worktrees or clones, virtual environments, and Pull Requests.
- One branch has one primary writer.
- Parallel work requires declared, non-overlapping write scopes.
- Shared contracts and foundation work merge before dependent tasks.
- Development may be parallel; integration into `main` is serial.
- Runtime concurrency remains a separate P0 architecture decision, with boundedness, isolation, cancellation, observability, backpressure, and deterministic cleanup already required.

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

1. Record the single-repository decision in ADR-001 and the Blueprint.
2. Establish an executable concurrent-development operating model.
3. Update decision status and agent rules.
4. Verify that packaging and source-layout questions remain unresolved.
5. Open a documentation-only Pull Request for project-lead review.

## Out of scope

- Production framework implementation.
- Source package or directory skeleton creation.
- Runtime dependency introduction.
- Selection or implementation of the runtime concurrency model.
- Package publication.
- Starting P1.

## Exit conditions for P0-D1

1. ADR-001 is merged and marked accepted.
2. The Blueprint confirms one canonical repository.
3. `P0_DECISION_STATUS.md` records single repository and concurrent-development governance as Confirmed.
4. `CONCURRENT_DEVELOPMENT.md` defines isolation, write scopes, dependencies, conflicts, worktrees, integration order, and handoff.
5. Distribution count, `src/`, directory layout, and runtime concurrency implementation remain Candidate.
6. The project lead performs the final merge.

P0 continues after P0-D1. P1 remains blocked.
