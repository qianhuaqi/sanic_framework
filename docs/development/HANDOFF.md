# Development Handoff

Updated at: 2026-06-28
Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Phase: P0 - Architecture Decision Review and Blueprint Consolidation
Parent Issue: #25
Active decision Issue: none
Active decision branch: none
Baseline: latest accepted `main`
Status: P0-D1 completed; awaiting next architecture decision

## Completed decision

### P0-D1: Single repository and concurrency governance

- Decision Issue: #31 — completed.
- Pull Request: #32 — merged.
- Merge commit: `92d6c0795fd5a6d21841a8ac3a1896d703809e40`.
- ADR-001: accepted.

Confirmed:

- LingShu uses one canonical repository: `qianhuaqi/lingshu`.
- Core, official capabilities, tests, documentation, tooling, and release metadata remain under one repository unless a future ADR proves otherwise.
- Concurrent developers use separate Issues, writer-prefixed branches, worktrees or clones, virtual environments, and Pull Requests.
- One branch has one primary writer.
- Every concurrent task declares base commit, write scope, dependencies, conflicts, integration order, and required checks.
- Independent tasks may run in parallel.
- Overlapping paths, duplicate public contracts, and cross-cutting files are serialized.
- Shared contracts and foundations merge before dependent work.
- Development may be parallel; integration into `main` is serial and controlled by the project lead.
- Runtime concurrency safety invariants are confirmed, while its concrete implementation remains unresolved.

## Active governance documents

- `docs/decisions/ADR-001-single-repository-and-concurrent-development.md`
- `docs/development/CONCURRENT_DEVELOPMENT.md`
- `docs/development/DEVELOPMENT_CONSTITUTION.md`
- `AGENTS.md`
- `docs/architecture/P0_DECISION_STATUS.md`
- `docs/architecture/LINGSHU_FRAMEWORK_BLUEPRINT.md`

## Still unresolved

- one Python distribution versus multiple distributions in the single repository;
- `packages/` versus another repository layout;
- direct `lingshu/` versus a `src/` layout;
- exact Core, HTTP, Server, Record, CLI, testing, and extension boundaries;
- event-loop, worker, process, thread, Task Group, admission-control, cancellation, and shutdown models;
- built-in versus separately installable capabilities;
- supported Python and platforms;
- release and compatibility policy;
- license and public governance files.

## Verification

The accepted P0-D1 change contains architecture and governance documentation only. No production source, package skeleton, runtime dependency, framework implementation, or publishing configuration was introduced.

P1 remains blocked.

## Next action

Select and document the next P0 architecture decision under Issue #25. Do not start production implementation.
