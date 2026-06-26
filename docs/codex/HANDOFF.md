# Development Handoff

Updated at: 2026-06-26
Location: office
Branch: codex/phase-b-lingshu-context
Worktree: clean
Work commit: cfb4847ae84efe7b7d1e3bfdb2d592608ef3a671

## Completed

- Error-code registry validation is included in `lingshu check`.
- Generated project `app/language/modules.ini` is an empty business registry with commented examples only.
- Generated projects now include `pyproject.toml`; the documented `python -m pip install -e ".[dev]"` command succeeds in a fresh venv after the framework wheel/editable dependency is available.
- The single `module_map_path()` API was removed; runtime uses merged registry paths.
- Request context cleanup is bound to Sanic response and exception lifecycle signals, plus an idempotent task completion callback for cancellation/disconnect paths.
- Wheel package data now includes LingShu built-in language files, the framework internal error-code registry, an internal manifest, and scaffold templates.
- `scripts/setup-dev.ps1` was added and smoke-tested.
- Root and generated `run.py` print an editable install hint when LingShu is not installed.
- Handoff scripts use a non-self-referential `Work commit` contract and pass real PowerShell behavior tests.

## Remaining

- Wait for Xiao Gu's fifth independent phase B acceptance after fourth-round fixes are pushed.

## Last verification

- editable install: passed with `.venv\Scripts\python.exe -m pip install -e ".[dev]"`
- pytest: 124 passed, 0 failed, 1 skipped
- contract check: Project check passed
- build: successfully built wheel and sdist
- diff check: passed
- cancellation cleanup: `tests\test_context_facade.py::test_request_context_clears_when_handler_task_is_cancelled` passed
- generated-project install smoke: `tests\test_init_project.py::test_initialized_project_editable_install_in_fresh_venv_without_pythonpath` passed with no `PYTHONPATH`
- wheel smoke: passed import, CLI, command absence, and wheel-content checks for language, registry, manifest, scaffold, and no `framework` package
- verify handoff: to be rerun after this handoff document update
- resume handoff: to be rerun after this handoff document update
- run.py smoke: missing-install environment printed the editable install hint

## Known risks

- GitHub has no CI configured; evidence is from local and temporary-venv verification.
- Direct `.ps1` execution is blocked by local execution policy; smoke uses `powershell -NoProfile -ExecutionPolicy Bypass`.
- Final remote HEAD must be recorded in the PR `[HANDOFF]` comment after this handoff document commit is pushed.

## Next exact action

- Run final handoff/resume verification, publish the final PR `[HANDOFF]` comment, and wait for Xiao Gu's fifth independent phase B acceptance.

## Current PR

- PR: #8
- Latest instruction: execute the latest two fourth-round independent acceptance comments; fourth-round blockers have been addressed locally and pushed.
