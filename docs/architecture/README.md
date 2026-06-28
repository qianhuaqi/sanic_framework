# LingShu Architecture Documents

## Current status

LingShu is in P0 architecture consolidation. No production implementation is authorized.

Read in this order:

1. `../development/DEVELOPMENT_CONSTITUTION.md`
2. `../development/CURRENT_PHASE.md`
3. `P0_DECISION_STATUS.md`
4. `LINGSHU_FRAMEWORK_BLUEPRINT.md`
5. accepted ADRs under `../decisions/`
6. `P0_HARDENING_CHECKLIST.md`

## Blueprint warning

`LINGSHU_FRAMEWORK_BLUEPRINT.md` is a detailed P0 design candidate, not a fully frozen implementation specification.

Its greenfield identity and independent-framework direction are confirmed. Its detailed repository layout, multi-package structure, distribution names, `src/` layout, exact component directories, extension packages, support matrix, and release-stage mapping remain candidates unless `P0_DECISION_STATUS.md` marks them Confirmed.

Do not create P1 source directories or packages from an unresolved Blueprint section.

## Single-design rule

The Blueprint remains the only overall architecture design document.

`P0_DECISION_STATUS.md` tracks confirmation state only. It does not define a competing architecture.

`P0_HARDENING_CHECKLIST.md` is a temporary consolidation checklist. Accepted items must be merged into the Blueprint before P0 acceptance, after which the checklist must be archived or replaced with verification evidence.
