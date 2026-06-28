# Development Handoff

Updated at: 2026-06-28
Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Phase: P0-D1 - Single Repository and Concurrency Governance
Issue: #31
Parent Issue: #25
Branch: `human/dodo/phase-p0-d1-single-repo-concurrency`
Baseline: latest accepted `main`
Status: ready for documentation review

## Decision from project lead

- LingShu uses a single canonical repository.
- Concurrency must be solved explicitly rather than avoided.

## Completed on this branch

- Added ADR-001 for the single-repository and concurrent-development model.
- Added `docs/development/CONCURRENT_DEVELOPMENT.md`.
- Confirmed one canonical repository in the Blueprint.
- Added development concurrency classes: independent, ordered dependency, conflicting, and cross-cutting exclusive.
- Required one Issue, branch, primary writer, worktree or clone, virtual environment, and Pull Request per concurrent task.
- Required every implementation Issue to declare base commit, write scope, dependencies, conflicts, integration order, and required checks.
- Established serial integration into `main` after parallel development.
- Established shared-contract-first merge ordering.
- Added agent rules for worktree and path isolation.
- Added runtime concurrency safety invariants while keeping its implementation model unresolved.
- Updated `P0_DECISION_STATUS.md` and `CURRENT_PHASE.md`.

## Confirmed scope

- Canonical repository: `qianhuaqi/lingshu`.
- No separate repositories for Core, HTTP, Server, Record, or official capabilities during initial development.
- No shared writable worktree between concurrent developers.
- No multiple primary writers on one branch.
- No parallel implementation with overlapping write scopes or duplicate public contracts.
- Development may run in parallel; merge into `main` is serial and controlled by the project lead.

## Still unresolved

- one Python distribution versus multiple distributions in the same repository;
- `packages/` or another package layout;
- direct `lingshu/` versus `src/`;
- exact component directories and package boundaries;
- event-loop, worker, process, thread, Task Group, admission-control, and shutdown models;
- supported Python and platforms;
- release and compatibility policy;
- license and public governance files.

## Verification

This branch changes architecture and governance documentation only. It adds no production source, package skeleton, runtime dependency, implementation, or publishing configuration.

Review must verify:

- the single-repository decision is not incorrectly expanded into a single-distribution decision;
- parallel work requires path isolation and declared dependency order;
- runtime concurrency safety requirements are recorded without prematurely selecting an implementation;
- P1 remains blocked.

## Next action

Review and merge the P0-D1 Pull Request. After merge, return to Issue #25 and decide the next unresolved architecture item. Do not start P1.
