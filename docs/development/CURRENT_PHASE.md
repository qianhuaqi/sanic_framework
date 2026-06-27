# Current Phase

Project: LingShu Framework
Current phase: C2-RC - Development Constitution V1 and Machine Boundary Tests
Current branch: codex/phase-c2-rc-development-constitution
Current issue: #21
Status: in progress
Next phase allowed: no

## Accepted Baseline

- Phase A accepted and merged.
- Phase B accepted and merged through PR #8.
- Phase C0 accepted and merged through PR #11.
- Phase C1 accepted and merged through PR #13.
- Phase C2.1 accepted and merged through PR #16.
- Phase C2.2A accepted and merged through PR #18.
- Phase C2-R0 accepted and merged through PR #20 (merge commit: `ed3ff04`).

## Test Baseline

- `tests/test_c2_auth.py`: 111 passed.
- `tests/test_c2_tenant.py`: 127 passed.
- Full suite: 446 passed, 1 skipped, 0 failed.
- `pip check`: no broken requirements.

## Phase C2-RC Goal

Establish Development Constitution V1 and machine-executable architecture
boundary tests. Freeze the rules that govern all developers (human and AI)
so that repository rules do not change when developers change.

This is a documentation and test phase — no production code changes.

## Scope

### In scope

- Rewrite `AGENTS.md` as a model-agnostic entry point.
- Create `docs/development/DEVELOPMENT_CONSTITUTION.md`.
- Create model-agnostic phase documents under `docs/development/`.
- Create architecture contract documents under `docs/architecture/`.
- Create ADRs under `docs/decisions/`.
- Create `docs/architecture/architecture-contract.json`.
- Create machine boundary tests under `tests/architecture/`.
- Update `tests/test_handoff_workflow.py` to use new fact sources.

### Out of scope

- Moving `src/lingshu` production directories.
- Modifying auth, tenant, RoutePolicy, database, Model, or Sanic adapter behavior.
- Starting R1–R6, C2.2B, or C3.
- Adding third-party dependencies.
