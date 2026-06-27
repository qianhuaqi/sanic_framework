# Task Template

This template defines the standard structure for every phase task. Copy it
into the GitHub Issue description or the phase's task document.

## Fact Sources

- GitHub Issue (current phase)
- Remote branch on `github`
- Pull Request and review comments
- `docs/development/DEVELOPMENT_CONSTITUTION.md`
- `docs/development/CURRENT_PHASE.md`
- `docs/architecture/architecture-contract.json`
- Related ADRs in `docs/decisions/`

## Allowed Scope

- (List specific deliverables, files, and changes permitted in this phase.)

## Prohibited Scope

- (List what must NOT be done in this phase.)

## Branch

- Branch name: (per convention)
- Base: `main`
- Remote: `github`

## Public API

- Stable API that must not change: (list)
- API changes permitted: (list or "none")

## Dependency Boundaries

- Per `docs/architecture/dependency-rules.md`.
- Per `docs/architecture/architecture-contract.json`.

## Test Contract

- Specialty suites: (list and minimum pass counts)
- Full suite minimum: 446 passed, 1 skipped, 0 failed
- Architecture tests: must pass
- `pip check`: no broken requirements
- `git diff --check`: no whitespace errors

## Commit Rules

- Commit message format: (specify)
- Stage only allowed files by explicit path.
- Never `git add .`.

## Reporting Format

1. Branch and HEAD SHA.
2. Changes made (by file).
3. Test results (specialty + full).
4. pip check / git diff --check.
5. Worktree status.
6. Any violations found.
7. Any deviations from the Issue (requires ADR + approval).
