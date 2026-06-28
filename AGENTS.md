# Repository Agent Rules

## Highest-priority project fact

LingShu is a greenfield, independently implemented Python Web/API framework.

It must not depend on Sanic, FastAPI, Flask, Django, Starlette, or another upper-level Web framework. Legacy repository code creates no compatibility obligation.

Any task, document, test, or implementation that assumes Sanic migration, Sanic adaptation, old API compatibility, or continuation of the legacy runtime must stop and be reported as a scope conflict.

## Sources of truth

1. Current GitHub Issue for the active phase.
2. `docs/architecture/LINGSHU_FRAMEWORK_BLUEPRINT.md` after project-lead confirmation.
3. Accepted ADRs under `docs/decisions/`.
4. `docs/development/CURRENT_PHASE.md`.
5. Remote phase branch and Pull Request.

Chat history and model memory are not permanent repository rules.

## Current phase restriction

P0 is architecture consolidation only. Do not create production framework source code, package skeletons, compatibility layers, or implementation PRs until the project lead explicitly freezes P0 and a P1 Issue is created.

## Development workflow

- One phase, one Issue, one branch, one PR.
- Never commit directly to `main`.
- Never auto-merge.
- The project lead holds final merge authority.
- Developers execute only the current Issue.
- Implementation and acceptance must remain separate.
- Never force push or rewrite protected history.

## Legacy archive

The old Sanic-based repository state is frozen at:

`archive/legacy-sanic-20260628`

Do not copy legacy source, tests, scaffolds, dependency files, or compatibility rules into the greenfield branch without an explicit Issue and architectural review.
