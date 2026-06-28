# Development Handoff

Updated at: 2026-06-28
Location: home
Writer: human
Branch: research/directory-release-roadmap
Worktree: clean
Baseline: b869270e0ec7cbc324d17ef246e39d0873aab14f
Work commit: b56f5e7a1c8308280e932fa486801827be84fc63

## Completed

- Created Issue #26 for the non-implementation directory and release-roadmap phase.
- Created research branch `research/directory-release-roadmap` from current `main`.
- Added ADR-006 recording the approved permanent root package `lingshu/` and
  the `core` / official `extensions` architecture.
- Added the canonical target directory plan.
- Added the release roadmap from v0.7.x through v1.0.0.
- Mapped reviewed C2-R1–R6 work into v0.8.0 through v0.11.0.
- Isolated the physical `src/lingshu/` to `lingshu/` move in v0.13.0.
- Added later gates for extension lifecycle, CLI/scaffold/docs/tools convergence,
  third-party extension SDK validation, beta hardening, and v1.0 stability.
- Updated `docs/development/CURRENT_PHASE.md` for C2-P1.
- Opened draft PR #27 targeting `main`.
- No production code, package configuration, Stable API, or physical directory
  was changed.

## Remaining

- Mark PR #27 ready after this handoff commit is visible remotely.
- Perform independent review of the ADR, directory boundaries, and release gates.
- Resolve review findings, if any, on this branch under Issue #26 scope.
- Xiao Gu must declare acceptance before merge.
- The project lead performs the final merge.
- After merge, create the v0.8.0/C2-R1 implementation Issue; do not begin it
  before PR #27 is merged.

## Last Verification

- Documentation scope review: completed.
- Production source diff: none intended.
- Automated test suite: not run in this GitHub-connected documentation session.
- Package build/install: not applicable to this planning-only change.
- Merge: not performed.

## Known Risks

- The active Development Constitution and `architecture-contract.json` still
  use current-state `src/lingshu/` ownership paths. This is intentional in this
  planning PR; they must be updated in their assigned implementation/planning
  phases rather than changed prematurely.
- Existing `src-migration-roadmap.md` remains as reviewed technical history.
  `docs/roadmap/RELEASE_ROADMAP.md` becomes the proposed release-level authority
  only after PR #27 is merged.
- Exact public extension class names and registration syntax are deliberately
  deferred to the v0.12.0 extension-contract ADR and implementation phase.

## Next Exact Action

- Review PR #27 against Issue #26 acceptance criteria and ADR-006.

## Current Issue

- Issue: #26
- PR: #27