# Development Handoff

Updated at: 2026-06-26
Location: office
Branch: codex/phase-b-lingshu-context
Worktree: clean
Work commit: f512b44c41ad20e319aaf12dfd5eec9a7099f9a6

## Completed

- Error-code registry validation is included in `lingshu check`.
- Generated project `app/language/modules.ini` is an empty business registry with commented examples only.
- Generated projects now include `pyproject.toml`; the documented `python -m pip install -e ".[dev]"` command succeeds in a fresh venv after the framework wheel/editable dependency is available.
- The single `module_map_path()` API was removed; runtime uses merged registry paths.
- Request context cleanup separates strict response/exception reset from task-end cancellation/disconnect detach.
- Cancellation/disconnect detach clears `request.ctx.lingshu_context`, marks the context completed, and releases token/raw request references without cross-context token reset.
- Wheel package data includes LingShu built-in language files, the framework internal error-code registry, and scaffold templates; the unused duplicate JSON manifest was removed.
- `scripts/setup-dev.ps1` was added and smoke-tested.
- Root and generated `run.py` print an editable install hint when LingShu is not installed.
- Handoff scripts use a non-self-referential `Work commit` contract and pass real PowerShell behavior tests.

## Remaining

- Wait for Xiao Gu's final confirmation after the fifth-round directed finalizer cleanup is pushed.

## Last verification

- editable install: passed with `.venv\Scripts\python.exe -m pip install -e ".[dev]"`
- pytest: 125 passed, 0 failed, 1 skipped
- contract check: Project check passed
- build: successfully built wheel and sdist
- diff check: passed
- cancellation cleanup: `tests\test_context_facade.py::test_request_context_clears_when_handler_task_is_cancelled` passed and asserts captured Sanic request/context detach state
- normal reset/no-op callback: `tests\test_context_facade.py::test_request_context_done_callback_is_noop_after_normal_reset` passed
- generated-project install smoke: `tests\test_init_project.py::test_initialized_project_editable_install_in_fresh_venv_without_pythonpath` passed with no `PYTHONPATH`
- wheel smoke: passed import, CLI, command absence, and wheel-content checks for language, registry, scaffold, no `framework` package, and no unused internal manifest JSON
- verify handoff: will be rerun after this handoff update commit
- resume handoff: last temporary clone smoke passed; rerun is not required for this directed code-only finalizer cleanup
- run.py smoke: missing-install environment printed the editable install hint

## Known risks

- GitHub has no CI configured; evidence is from local and temporary-venv verification.
- Direct `.ps1` execution is blocked by local execution policy; smoke uses `powershell -NoProfile -ExecutionPolicy Bypass`.
- Final remote HEAD must be recorded in the PR `[HANDOFF]` comment after this directed handoff update is pushed.

## Next exact action

- Run final handoff verification, publish the final PR `[HANDOFF]` comment, and wait for Xiao Gu's final Phase B confirmation.

## Current PR

- PR: #8
- Latest instruction: execute the fifth-round directed finalizer cleanup; scope limited to cancellation finalizer semantics, effective tests, and unused manifest removal.
