# Development Handoff

Updated at: 2026-06-28
Phase: P0-G1 - Governance and Architecture Fact-Source Consolidation
Branch: `human/dodo/phase-p0-g1-governance-hardening`
Issue: #25
Baseline: `main` after PR #28
Status: ready for review

## Confirmed repository state

- PR #28 is merged.
- The active `main` tree is the greenfield P0 baseline.
- The previous Sanic-based repository is archived at `archive/legacy-sanic-20260628`.
- Archive commit: `b869270e0ec7cbc324d17ef246e39d0873aab14f`.
- Production source, legacy tests, old scaffolds, and old dependency configuration are absent from the active tree.
- P0 remains unaccepted and P1 remains blocked.

## Completed on this branch

- Expanded `DEVELOPMENT_CONSTITUTION.md` into an executable governance contract.
- Synchronized `CURRENT_PHASE.md` with the post-PR #28 state.
- Marked ADR-000 as accepted and recorded the effective merge.
- Updated `AGENTS.md` with reading order, conflict handling, P0 gates, dependency rules, security rules, and archive restrictions.
- Expanded README with actual repository status and contributor entrypoints.
- Added `P0_DECISION_STATUS.md` to separate confirmed, rejected, and candidate architecture decisions.
- Added `docs/architecture/README.md` with a visible architecture reading order and candidate-design warning.
- Replaced the stale v0.6 Blueprint entry with a controlled P0-RC0 document containing only confirmed direction, explicit open decisions, and implementation gates.
- Preserved the complete former v0.6 detailed design unchanged at `docs/architecture/candidates/LINGSHU_FRAMEWORK_BLUEPRINT_V0.6_CANDIDATE.md`.
- Explicitly marked package, multi-distribution, `src/`, directory, extension, support, and release layouts as non-executable candidates.
- Updated Issue #25 to match the active P0-G1 branch and current governance rules.
- Closed legacy Issue #12 as not planned.
- Confirmed that Issue #25 is the only open repository Issue.

## Verification

Compared with `main`, this branch contains governance and architecture-document changes only. No production source, dependency configuration, package skeleton, runtime implementation, or publishing configuration has been added.

The former detailed Blueprint content is preserved byte-for-byte as a candidate document; it is no longer the active architecture entrypoint.

Runtime tests are not applicable because this phase contains documentation and governance only. Review must verify internal consistency, fact-source ordering, P0 gates, and absence of implementation authorization.

## Remaining after merge

- Review each detailed candidate chapter with the project lead.
- Decide the final repository and package layout.
- Decide whether any `src/` layout will be used.
- Decide component and official-extension boundaries.
- Integrate accepted `P0_HARDENING_CHECKLIST.md` requirements into the single Blueprint.
- Decide license, contribution, vulnerability-reporting, and release policies.
- Prepare P1 scope only after those decisions are confirmed.

## Known repository history noise

During the preceding audit, three temporary files were accidentally committed directly to `main` and immediately removed. No temporary file remains in the tree. The six corrective/no-op commits remain visible because shared history was not rewritten.

Affected commit sequence:

- `eb12c697` / `5c7e5f54`;
- `4c88089a` / `5550e75f`;
- `333b90b2` / `788e3bf2`.

No production or governance file remains changed by those temporary commits.

## Next action

Review PR #29. Do not start P1.
