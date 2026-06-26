# Development Handoff

Updated at: 2026-06-26
Location: office
Branch: codex/phase-b-lingshu-context
Worktree: clean
Work commit: d3f9d13295d848ce507c2f11ed10349c8dc6cf0c

## Completed

- Error-code registry validation is included in `lingshu check`.
- Generated project `app/language/modules.ini` is an empty business registry with commented examples only.
- The single `module_map_path()` API was removed; runtime uses merged registry paths.
- Request context cleanup is bound to Sanic response and exception lifecycle signals with idempotent reset.
- `scripts/setup-dev.ps1` was added and smoke-tested.
- Root and generated `run.py` print an editable install hint when LingShu is not installed.
- Handoff scripts use a non-self-referential `Work commit` contract and pass real PowerShell behavior tests.

## Remaining

- Wait for Xiao Gu's fourth independent phase B acceptance after fixes are pushed.

## Last verification

- editable install: passed with `.venv\Scripts\python.exe -m pip install -e ".[dev]"`
- pytest: 122 passed, 0 failed
- contract check: Project check passed
- build: successfully built wheel and sdist
- diff check: passed
- verify handoff: exited 0 and printed `Handoff verification passed`
- resume handoff: temporary clone exited 0 and printed current HEAD plus HANDOFF
- wheel smoke: passed import, CLI, command absence, and wheel-content checks
- run.py smoke: missing-install environment printed the editable install hint

## Known risks

- GitHub has no CI configured; evidence is from local and temporary-venv verification.
- Direct `.ps1` execution is blocked by local execution policy; smoke uses `powershell -NoProfile -ExecutionPolicy Bypass`.
- Final remote HEAD must be recorded in the PR `[HANDOFF]` comment after this handoff document commit is pushed.

## Next exact action

- Publish the final PR `[HANDOFF]` comment and wait for Xiao Gu's fourth independent phase B acceptance.

## Current PR

- PR: #8
- Latest instruction: wait for fourth independent phase B acceptance after final handoff.
