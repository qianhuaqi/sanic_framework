# Development Handoff

Updated at: 2026-06-26
Location: office
Branch: codex/phase-c1-request-runtime
Worktree: clean
Work commit: 5cbbf4a3d2c75fbbfde3f4e38b4a2b8e9a7c6d10

## Worker

- Model: .qwen-cli / Qwen Code
- Baseline HEAD: 309fb40fd910bcc8dc474e0247012536d359ad3f
- Second-round review: PR #13, Review ID 4577914519

## Completed

### P0: execution_id isolation

- Added framework-internal `execution_id` field to `RequestExecutionContext`, auto-generated per request via `uuid4().hex`, never accepted from client headers.
- `TaskRecord` captures `execution_id` at spawn time.
- `finish_request()` now matches request-scoped tasks by `execution_id` instead of client-controllable `request_id`.
- Two concurrent requests with the same `X-Request-ID` can no longer cancel each other's request-scoped tasks.

### P0: Unified idempotent request finalizer

- Implemented `finalize_request_context()` in `sanic_adapter.py` with `request.ctx.lingshu_finalized` guard for idempotency.
- Core structure: `try: await cleanup_tasks → except: record → finally: release_inflight_once + reset_context_once`.
- In-flight tracker release and context reset happen unconditionally regardless of task cleanup success, failure, or timeout.
- Deadline-exhausted requests still get a minimum 0.5s cleanup budget (capped at 2.0s).
- `CancelledError` propagates after cleanup completes.

### P0: Cancellation and disconnect full cleanup

- `policy.py` handler wrapper now uses `try/except/finally` around the real handler.
- Normal return, business exception, timeout, and `CancelledError` all enter the unified finalizer.
- `CancelledError` sets `CLIENT_DISCONNECT` reason if none set, then re-raises.
- Done callback demoted to synchronous last-resort leak guard only: marks finalized, safely returns tracker, detaches references. Never resets ContextVar tokens.

### P0: Drain moved to before_server_stop

- Main shutdown coordinator now runs at `before_server_stop` listener.
- `after_server_stop` only does idempotent fallback `shutdown()` call.
- Teardown cleanup registered once per coordinator lifecycle via `lingshu_teardown_registered` flag, reset when coordinator is rebuilt.

### P1: Cleanup continues after single timeout

- Removed `break` after single-cleanup `TimeoutError`.
- Changed to `continue` so subsequent cleanups run if total budget remains.
- Only breaks when `remaining <= 0`.

### P1: Route deadline vs handler TimeoutError

- Replaced `asyncio.wait_for(handler, timeout=remaining)` with `asyncio.timeout_at(execution.deadline)`.
- `TimeoutError` is only treated as route deadline when `now >= execution.deadline`.
- Handler-raised `TimeoutError` propagates as a normal exception (not 504/990002).

### P1: functools.wraps

- Handler wrapper uses `@wraps(handler)` preserving `__name__`, `__module__`, `__doc__`, `__annotations__`, `__wrapped__`.
- Custom attributes `__lingshu_route_policy__` and `__lingshu_compiled_policy__` explicitly copied.

### P1: Task history sanitization

- Results summarized via `_summarize_result()`: None/bool/int/float kept as-is, strings truncated to 200 chars, other types replaced with `<TypeName>`.
- Exceptions summarized via `_summarize_exception()`: stores type name + truncated (500 char) redacted message only.
- Sensitive fields redacted via regex: `password`, `passwd`, `token`, `secret`, `authorization`, `api_key`, `access_key`.
- No traceback objects or original exception references retained.

## Remaining

- Wait for Xiao Gu third-round Phase C1 acceptance.

## Last verification

- editable install: passed with `.venv\Scripts\python.exe -m pip install -e ".[dev]"`
- pytest: 169 passed, 0 failed (C1), 1 skipped; 4 pre-existing failures in test_config/test_extensions/test_init_project (local MySQL environment, unrelated to C1)
- contract check: Project check passed
- build: successfully built wheel and sdist
- diff check: passed (no whitespace errors)
- wheel content smoke: 82 files, no `framework/` package, built-in languages present
- health endpoint smoke: `/live`=200 `/ready`=200 `/health`=200 state=ready
- route timeout smoke: status=504 code=990002
- handler TimeoutError smoke: status=500 code=990000 (not 990002)
- shutdown/drain smoke: state=stopped in_flight=0

## Known risks

- GitHub has no CI configured; evidence is from local Windows verification.
- 4 pre-existing test failures (test_config, test_extensions, test_init_project) are caused by local MySQL environment configuration and are not related to C1 changes.
- Sanic ASGI test client triggers server stop listeners between requests; lifecycle restart support handles this.
- C1 intentionally does not implement JWT, authorization, tenant resolution, HMAC, rate limiting, idempotency, ORM/Redis/Mongo redesign, OpenAPI, complete DI, events or C2 behavior.

## Next exact action

- Wait for Xiao Gu's third-round Phase C1 review.

## Current PR

- PR: #13
- Review ID addressed: 4577914519
- C2 status: not started
