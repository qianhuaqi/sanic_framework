# Current Phase

Project: LingShu Framework
Current phase: C2-R0 - src architecture audit, boundary freeze, and migration plan
Current branch: research/c2-src-convergence
Current issue: #19
Status: architecture audit complete, awaiting review
Next phase allowed: no

## Accepted Baseline

- Phase A accepted and merged.
- Phase B accepted and merged through PR #8.
- Phase C0 accepted and merged through PR #11.
- Phase C1 accepted and merged through PR #13.
- Phase C2.1 accepted and merged through PR #16 (merge commit: `398d042`).
- Phase C2.2A accepted and merged through PR #18 (merge commit: `2fc6e6b`).

## Phase C2-R0 Goal

Architecture audit of the entire `src/lingshu` codebase: identify structural
debt, overlapping modules, circular dependencies, and hot files. Define target
layer boundaries and a phased migration roadmap (C2-RC, then C2-R1 through C2-R6).

This is a design-only phase — no production code changes.

## Deliverables

- `docs/architecture/src-convergence-audit.md` — full module inventory, dependency
  analysis, overlap matrix, hot files, technical-debt priority.
- `docs/architecture/src-target-boundaries.md` — target directory structure,
  layer dependency rules, app-scoped cleanup registry, auth/adapter separation,
  no `public/` decision, tenant positioning.
- `docs/architecture/src-migration-roadmap.md` — phased migration plan with
  C2-RC prerequisite gate, API stability tiers, deprecation cycle, R1-R6.

## Test Baseline

- `tests/test_c2_tenant.py`: 127 passed, 0 failed.
- `tests/test_c2_auth.py`: 111 passed, 0 failed.
- Full suite: 446 passed, 1 skipped, 0 failed.
- `pip check`: no broken requirements.
- No production code modifications.

## Scope Boundaries

### In scope (C2-R0)

- Read-only analysis of `src/lingshu`.
- Documentation: audit, boundaries, roadmap.
- CURRENT_PHASE.md update.

### Out of scope (prohibited)

```text
Moving directories
Deleting code
Modifying imports
Modifying public API
Starting C2-RC implementation
Starting C2-R1 through C2-R6 implementation
Starting C2.2B or C3
```

## Branch And Tracking

- Branch: `research/c2-src-convergence`
- Issue: `#19`
