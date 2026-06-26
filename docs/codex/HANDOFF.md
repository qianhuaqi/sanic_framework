# Development Handoff

Updated at: 2026-06-26
Location: office
Branch: codex/phase-c1-request-runtime
Worktree: clean
Base HEAD: 330c6593ed7251ca3473c7834b2dfe39c276a40d

## Worker

- Model: .qwen-cli / GLM-5.2
- Baseline HEAD: 330c6593ed7251ca3473c7834b2dfe39c276a40d
- Third-round review: PR #13, Review ID 4578251994

## Completed (Third-Round Direct Remediation)

### P0: Python 3.10 runtime compatibility restored

- Replaced `enum.StrEnum` (3.11+) with `str, Enum` for `CancellationReason` and `LifecycleState`. Value semantics unchanged: `.value` returns string, `==` comparison with string literals preserved.
- Replaced `asyncio.create_task(coro, context=ctx)` (3.11+ keyword) with `ctx.run(asyncio.create_task, coro, name=...)` for application/operation scoped tasks. Request-scoped tasks use `copy_context()` as before.
- Application/operation tasks confirmed to run under a clean context — cannot read `current_execution`.
- AST-level source assertions in tests verify no `StrEnum`, no `asyncio.timeout_at`, and no `create_task(..., context=...)` remain in `src/lingshu/system/`.

### P0: Exact route deadline attribution

- Replaced `asyncio.timeout_at(execution.deadline)` (3.11+) with `asyncio.wait((handler_task,), timeout=remaining)` pattern.
- Handler runs as a locally-owned `handler_task` created via `asyncio.ensure_future`. This guarantees:
  - If handler completes before deadline: `await handler_task` returns result or raises its own exception (including `TimeoutError`) as-is — never 504/990002.
  - If deadline expires: `handler_task.cancel()` + `asyncio.gather(handler_task, return_exceptions=True)` ensures no orphan task.
  - If wrapper is cancelled: handler_task is cancelled and awaited before re-raising `CancelledError`.
  - `remaining <= 0` at entry: immediate 504/990002 without starting handler.
- Handler that raises `TimeoutError` after deadline is still treated as handler exception (not route deadline), because the task is already done when `asyncio.wait` returns.

### P0: Full-suite baseline comparison

- Created temporary git worktree at pre-C1 commit `d571602cb0e83b7abe49a3f1b53e43dbeb2d2aa8` for controlled baseline comparison.
- Same Python version (3.11.8), same dependencies, same environment, same pytest command for both.
- Current branch: 203 passed, 4 failed, 1 skipped.
- Baseline: 120 passed, 5 failed, 1 skipped.
- The 3 failures common to both: `test_config::test_load_config_defaults_disable_databases`, `test_extensions::test_no_database_enabled_by_default`, `test_extensions::test_require_database_raises_clear_error` — all MySQL environment configuration issues.
- The 4th current failure (`test_init_project::test_initialized_project_make_module_is_registered`) exists in baseline too, with identical root cause (`pymysql.err.ProgrammingError: Table 'quant.demo' doesn't exist`). In the current branch the exception surfaces through `deadline_wrapper` at `policy.py:178` which is the expected handler call path; the root cause is the missing MySQL table, not the wrapper.
- The baseline has a 5th failure (`test_handoff_workflow::test_current_phase_and_handoff_docs_exist_with_phase_b_context`) that the current branch has fixed — it now correctly reflects Phase C1 instead of Phase B/C0.
- **Conclusion: Current branch introduces zero new regressions.** Worktree removed after comparison.

### P0: Python 3.10 verification

- Machine Python: 3.11.8 (confirmed via pytest session header). No Python 3.10 interpreter installed on this machine.
- Compatibility verified through:
  1. AST/source-level regex assertions scanning all `src/lingshu/system/**/*.py` files.
  2. Runtime type checks: `CancellationReason` and `LifecycleState` confirmed as `str, Enum` subclasses, not `StrEnum`.
  3. `context.run(asyncio.create_task, ...)` pattern verified to work correctly on 3.11.
- HANDOFF transparency: **Python 3.10 interpreter was not available for real test execution on this machine.** Compatibility is ensured by code-level enforcement and AST assertions, not by 3.10 runtime verification.

### P1: Exception redaction completeness

- Expanded `_SENSITIVE_PATTERN` to cover all required formats:
  - `Authorization: Bearer abc123` / `Authorization: Basic abc123` — full credential redacted.
  - `{"token":"abc123"}` / `{'token': 'abc123'}` — JSON double/single quote keys.
  - `api_key = "abc123"` / `password: abc123` / `secret = abc123` / `access-key: abc123` — colon, equals, space, quote variants.
- Redaction preserves surrounding quotes so JSON structure is not broken.
- Finalizer log (`sanic_adapter.py`) no longer writes raw `str(exc)`. Uses `_summarize_exception()` to emit only exception type name + safe/redacted message.
- `_sanitize_text()` applies `_truncate()` internally at 500 chars.

### P1: Deterministic concurrency tests

- Cancellation test uses `asyncio.Event` synchronization: handler sets `entered` event → test cancels → test waits for `cleanup_done` event. No fixed-duration `sleep` for business state.
- Concurrent request task isolation test uses explicit `started`/`finished` Events.
- `await asyncio.sleep(0)` used only for single event-loop yield, not for timing assertions.

### P1: Stop listener ordering verification

- Tests record exact event sequence: `setup` → `teardown`, verifying `before_server_stop` runs coordinator (which includes teardown) before `after_server_stop` fallback.
- Teardown count asserted to be exactly 1 across full ASGI start/stop lifecycle.
- `after_server_stop` re-invocation confirmed idempotent — teardown does not run twice.
- Cleanup registration count confirmed not to accumulate across multiple ASGI start/stop cycles.

## Remaining

- Wait for Xiao Gu final Phase C1 acceptance.

## C1 directed tests

```
python -m pytest tests/test_c1_execution_context.py tests/test_c1_lifecycle.py tests/test_c1_task_registry.py tests/test_c1_review_regressions.py tests/test_c1_third_round_review.py tests/test_context_facade.py -q
→ 92 passed in 1.92s
```

## Full test suite

```
python -m pytest tests -q
→ 203 passed, 4 failed, 1 skipped in 106.21s
```

## Baseline comparison

- Baseline commit: `d571602cb0e83b7abe49a3f1b53e43dbeb2d2aa8`
- Baseline result: 120 passed, 5 failed, 1 skipped
- Current result: 203 passed, 4 failed, 1 skipped
- Common failures (MySQL environment): 3 tests
- 4th failure (test_init_project): identical root cause in both branches (`pymysql.err.ProgrammingError: Table 'quant.demo' doesn't exist`)
- Baseline-only failure (test_handoff_workflow phase-B context): fixed in current branch
- **Current branch introduces zero new regressions.**

## Python 3.10 verification

- Machine interpreter: Python 3.11.8 — no 3.10 installed.
- Verified via AST source assertions (no StrEnum, no timeout_at, no context= kwarg) + runtime type checks.
- **Not verified on real 3.10 interpreter.**

## Build

```
python -m build
→ Successfully built lingshu_framework-0.2.0.tar.gz and lingshu_framework-0.2.0-py3-none-any.whl
```

## Contract check

- `git diff --check`: passed (no whitespace errors)

## Smoke

- `/live` `/ready` `/health`: 200 state=ready (verified via C1 test suite)
- Route deadline: 504/990002 (verified)
- Handler TimeoutError: 500/990000 not 990002 (verified)
- Cancellation + cleanup: in_flight=0, no orphan tasks (verified via Event-synchronized test)
- before_server_stop drain: state=stopped (verified)
- after_server_stop idempotent fallback: teardown runs once (verified)

## Timeout attribution

- RoutePolicy deadline → 504/990002, handler_task cancelled and awaited.
- Handler-raised TimeoutError → propagates as normal exception, never 990002.
- Handler completed after deadline → handler result/exception returned.

## Redaction

- Bearer/Basic credentials: fully redacted.
- JSON double/single quote tokens: fully redacted.
- api_key/password/secret/access-key (colon/equals): fully redacted.
- Finalizer log: exception type + safe summary only, no raw str(exc).
- Non-sensitive text (e.g. `localhost:5432`) preserved.

## Listener order

- before_server_stop → shutdown coordinator → teardown → state=stopped.
- after_server_stop → idempotent fallback, no re-teardown.
- Cleanup registration does not accumulate across ASGI cycles.

## Known risks

- GitHub has no CI configured; all evidence is from local Windows verification.
- 4 pre-existing failures (test_config, test_extensions, test_init_project) caused by local MySQL environment configuration. Baseline comparison confirms these are not new regressions.
- Python 3.10 interpreter not available on this machine for real test execution.
- Sanic ASGI test client triggers server stop listeners between requests; lifecycle restart support handles this.
- C1 intentionally does not implement JWT, authorization, tenant resolution, HMAC, rate limiting, idempotency, ORM/Redis/Mongo redesign, OpenAPI, complete DI, events or C2 behavior.

## Next exact action

- Wait for Xiao Gu's final Phase C1 acceptance.

## Current PR

- PR: #13
- Review ID addressed: 4578251994
- C2 status: not started
- Merge status: not merged, awaiting Xiao Gu final acceptance
