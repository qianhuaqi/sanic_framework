# src Target Boundaries (Revised)

Phase: C2-R0 (first-round review remediation)
Issue: #19

## 1. Decisions

### 1.1 No `public/` directory (Option A chosen)

**Decision:** Keep existing top-level facades (`lingshu.auth`, `lingshu.tenant`,
`from lingshu import request/db/config/logger`). Do NOT create a `public/`
directory.

**Rationale:**
- The stable public API surface already consists of thin top-level facade
  modules that re-export from `system.*`. They are well-tested (C2.1 and C2.2A
  both verify the facade pattern end-to-end).
- Adding `public/` would create a third layer (facade → public → system),
  increasing indirection without clear benefit.
- Business code already imports `from lingshu.auth import ...` and
  `from lingshu import request`. Moving these to `lingshu.public.auth` would
  be a breaking change for all existing user projects.
- If internal organization is needed, the facade modules can re-export from
  relocated implementation packages (e.g. `contrib/tenant/`) without changing
  the public import path.

### 1.2 Auth and adapter dependency separation

**Decision:** Split auth/tenant into pure domain types + Sanic adapter middleware.

```
security/auth/
  ├── principal.py        Pure dataclass, no Sanic dependency
  ├── result.py           Pure enum + outcome, no Sanic dependency
  ├── authenticator.py    Protocol + Chain, no Sanic dependency
  ├── context.py          ContextVar binding, no Sanic dependency
  ├── jwt_bearer.py       JWT authenticator (imports PyJWT, not Sanic)
  └── stub_authenticator.py  Test-only

adapters/sanic/
  └── auth_middleware.py  Sanic middleware, imports security/auth
```

**Rationale:**
- The previous design allowed `security/auth -> adapters/sanic`, which makes
  the entire auth package depend on Sanic. This contradicts the goal of a
  portable auth domain.
- Correct direction: `security/auth` defines types and protocols with zero
  Sanic dependency. `adapters/sanic/auth_middleware` depends on `security/auth`
  to install the middleware and build 401 responses.
- Tenant follows the same pattern: `contrib/tenant/` holds pure types and
  resolvers; `adapters/sanic/tenant_middleware.py` holds the Sanic middleware.

**Dependency arrows:**
```
adapters/sanic/auth_middleware   → security/auth (types, protocols)
adapters/sanic/tenant_middleware → contrib/tenant (types, resolvers)
contrib/tenant                   → security/auth (needs Principal)
security/auth                    → core/ (ContextVar, errors)
```

Auth does NOT depend on adapter. Adapter depends on auth. One-way.

### 1.3 Tenant module positioning

**Decision:** Tenant moves from `system/auth/tenant/` to `contrib/tenant/`.

**Rationale:**
- Tenant is an optional capability, not part of core authentication.
- Auth must work correctly without tenant installed.
- `contrib/tenant/` depends on `security/auth/` (needs Principal), but
  `security/auth/` never imports `contrib/tenant/`.

## 2. App-Scoped Cleanup Registry

### 2.1 Rejection of module-level global registry

**Rejected pattern (from initial proposal):**
```python
# REJECTED — module-level global state
_cleanup_hooks: list[Callable] = []

def register_request_cleanup(hook):
    _cleanup_hooks.append(hook)
```

**Problems:**
- Multiple Sanic apps in the same process share the same hook list.
- Import-time registration causes test ordering pollution.
- Optional capabilities (e.g. tenant) cannot be cleanly uninstalled.
- No idempotency guarantee across re-imports or re-installs.

### 2.2 App-scoped registry design

**Target pattern:**
```python
# adapters/sanic/cleanup_registry.py (design only — not implemented in R0)

class AppCleanupRegistry:
    """Per-app registry for request cleanup hooks."""

    def __init__(self):
        # hook_id → CleanupHook(fn, order)
        self._hooks: dict[str, CleanupHook] = {}

    def register(self, hook_id: str, hook: Callable, *, order: int = 0) -> None:
        existing = self._hooks.get(hook_id)
        if existing is not None:
            # Same hook_id + same callable → idempotent no-op
            if existing.fn is hook:
                return
            # Same hook_id + DIFFERENT callable → configuration error
            # raised at install time, not at request time
            raise CleanupConfigError(
                hook_id=hook_id,
                existing_fn=existing.fn,
                new_fn=hook,
            )
        self._hooks[hook_id] = CleanupHook(id=hook_id, fn=hook, order=order)

    def unregister(self, hook_id: str) -> None:
        self._hooks.pop(hook_id, None)

    async def run_all(self, raw_request, *, reason: str | None = None) -> None:
        """Run all registered hooks in order.

        Each hook is individually marked as completed. A hook that has
        already run for this request is NOT re-run.
        """
        completed = getattr(raw_request.ctx, "_lingshu_completed_hooks", None)
        if completed is None:
            completed = set()
            raw_request.ctx._lingshu_completed_hooks = completed

        errors: list[CleanupError] = []
        for hook in sorted(self._hooks.values(), key=lambda h: h.order):
            if hook.id in completed:
                continue  # per-hook idempotency — skip already-completed hooks

            try:
                result = hook.fn(raw_request)
                if inspect.isawaitable(result):
                    await result
                completed.add(hook.id)  # mark AFTER successful completion
            except asyncio.CancelledError:
                # Necessary ContextVar/binding resets for previously-completed
                # hooks are already done. Re-raise CancelledError after this
                # hook's necessary cleanup — the outer caller re-propagates.
                # This hook is NOT marked complete; it will be retried if
                # run_all is called again (e.g. by a final cleanup pass).
                raise
            except Exception as exc:
                errors.append(CleanupError(hook_id=hook.id, error=exc))
                logger.warning(
                    "cleanup hook %s failed: %s",
                    hook.id,
                    _summarize_exception(exc),
                )
                # Even on error, mark as completed so we don't retry a
                # failing hook in a subsequent cleanup pass.
                completed.add(hook.id)

        if errors:
            raw_request.ctx._lingshu_cleanup_errors = errors
```

### 2.3 Registry semantics

| Property | Specification |
|---|---|
| **Scope** | One registry per Sanic app instance (`app.ctx.cleanup_registry`) |
| **Hook ID** | String, unique within the registry. |
| **Duplicate registration (same callable)** | `register()` with same `hook_id` AND same `fn` object → idempotent no-op. |
| **Conflicting registration (different callable)** | `register()` with same `hook_id` but different `fn` → raises `CleanupConfigError` at install time. This is a configuration error, not a runtime error. |
| **Order** | Integer, ascending. Default 0. Hooks with same order run in registration order. |
| **Per-hook completion tracking** | Each request records `_lingshu_completed_hooks: set[str]` on `request.ctx`. A hook's ID is added to this set **only after it completes** (success or exception). A hook that has already completed is skipped on subsequent `run_all()` calls. |
| **No pre-set done flag** | The registry MUST NOT set a global `_lingshu_cleanup_done = True` before hooks run. Individual hook completion is tracked, not bulk completion. |
| **CancelledError** | Always propagated. Necessary ContextVar/binding resets from previously-completed hooks are already applied. The cancelled hook is NOT marked complete. The outer caller re-raises `CancelledError` after any final necessary cleanup. |
| **Deadline exhausted** | If the request deadline is exhausted, necessary context cleanup (ContextVar resets, binding teardown) MUST still execute in a bounded cleanup section. Deadline exhaustion does NOT skip necessary cleanup. |
| **Other exceptions** | Caught, logged at WARNING level with sanitized summary. Does NOT stop subsequent hooks. Errors are aggregated in `request.ctx._lingshu_cleanup_errors`. The failed hook IS marked complete (no retry). |
| **Timeout** | Each hook inherits the request's remaining deadline. The registry does not impose its own timeout — that is the policy compiler's job. |
| **Multi-app isolation** | Each app has its own `AppCleanupRegistry` instance. No shared global state. |
| **Registration timing** | Registered during middleware installation (not import time). `install_auth_middleware(app)` registers the auth cleanup hook. `install_tenant_middleware(app)` registers the tenant cleanup hook. |
| **No silent swallowing** | `except Exception: pass` is FORBIDDEN. All exceptions are logged with sanitized summaries and aggregated. |

### 2.4 Registration example (design only)

```python
# adapters/sanic/auth_middleware.py
def install_auth_middleware(raw_app):
    registry = get_cleanup_registry(raw_app)
    registry.register("auth:principal_reset", _cleanup_principal_binding, order=10)
    # ... install middleware ...

async def _cleanup_principal_binding(raw_request):
    binding = getattr(raw_request.ctx, "lingshu_principal_binding", None)
    if binding is not None and not binding.reset_done:
        binding.__exit__(None, None, None)
```

## 3. Target Directory Structure

```
src/lingshu/
├── core/                         Framework core — zero external deps
│   ├── __init__.py
│   ├── context.py                ContextVar management
│   ├── execution.py              RequestExecutionContext (deadline, cancel)
│   ├── errors.py                 Framework exception hierarchy
│   ├── types.py                  _deep_freeze, Binding protocol (shared)
│   └── policy.py                 RoutePolicyDefinition + CompiledRoutePolicy
│
├── adapters/
│   └── sanic/                    Sanic integration layer
│       ├── __init__.py
│       ├── context_middleware.py install_context_middleware + request lifecycle
│       ├── resource_registry.py  set_resource/get_resource/get_app_config
│       ├── cleanup_registry.py   AppCleanupRegistry (app-scoped, per §2)
│       ├── finalize.py           finalize_request_context (uses cleanup registry)
│       ├── health.py             install_health_routes
│       ├── policy_compiler.py    RoutePolicyCompiler
│       ├── auth_middleware.py    Auth middleware (depends on security/auth)
│       └── tenant_middleware.py  Tenant middleware (depends on contrib/tenant)
│
├── security/
│   └── auth/                     Pure auth domain (no Sanic dependency)
│       ├── __init__.py
│       ├── principal.py
│       ├── result.py
│       ├── authenticator.py
│       ├── context.py            ContextVar binding
│       ├── jwt_bearer.py
│       └── stub_authenticator.py
│
├── contrib/
│   └── tenant/                   Optional tenant resolution (no Sanic dependency)
│       ├── __init__.py
│       ├── context.py
│       ├── result.py
│       ├── resolver.py
│       ├── binding.py
│       ├── claim_resolver.py
│       └── stub_resolver.py
│
├── data/
│   ├── database/                 Database wrappers
│   ├── model/                    ORM (BaseModel only in data core)
│   └── dependencies.py
│
├── compat/                       Legacy compatibility shims
│   ├── auth.py
│   ├── signing.py
│   ├── maintenance.py
│   ├── cache.py
│   ├── params.py
│   ├── crypt.py
│   └── json_encoder.py
│
├── app.py                        Factory (composition only)
├── auth.py                       Public facade (stays at top level)
├── tenant.py                     Public facade (stays at top level)
├── config.py
├── response.py
├── exception.py
├── error_codes.py
├── versioning.py
├── logging.py
├── middleware_registry.py
├── controller.py
├── helper.py
├── runtime.py
├── i18n.py
│
├── cli/
├── scaffold/
├── language/                     Framework built-in messages
├── resources/
└── view/
```

## 4. Layer Dependency Rules

### 4.1 `core/`

| Rule | Detail |
|---|---|
| May import | Standard library only |
| Must NOT import | Sanic, JWT, database drivers, any other lingshu package |
| Public API | ContextVars, RequestExecutionContext, RoutePolicyDefinition, _deep_freeze, Binding |

### 4.2 `adapters/sanic/`

| Rule | Detail |
|---|---|
| May import | `core/`, `security/auth/` (types only), `contrib/tenant/` (types only), `response.py`, Sanic (directly, as needed) |
| Must NOT import | `data/`, `compat/`, legacy `middleware/` |
| Public API | install functions, finalize, cleanup registry, health routes |

### 4.3 `security/auth/`

| Rule | Detail |
|---|---|
| May import | `core/`, PyJWT (in `jwt_bearer.py` only) |
| Must NOT import | Sanic, `adapters/`, `contrib/tenant/`, `data/`, `compat/` |
| Public API | Principal, Authenticator, AuthenticatorChain, AuthenticationOutcome |

### 4.4 `contrib/tenant/`

| Rule | Detail |
|---|---|
| May import | `core/`, `security/auth/` (needs Principal) |
| Must NOT import | Sanic, `adapters/`, `data/`, `compat/` |
| Public API | TenantContext, TenantResolver, TenantResolverChain, ClaimTenantResolver |

### 4.5 `data/`

| Rule | Detail |
|---|---|
| May import | `core/`, third-party drivers (aiomysql, motor, redis) |
| Must NOT import | Sanic, `adapters/`, `security/`, `contrib/`, `compat/` |
| Note | `BusinessModel` does NOT belong in `data/model/` — it is a project service-layer pattern (couples to request lifecycle, auth principal, tenant context). R6 only decouples it from global proxies; old paths kept with `DeprecationWarning`. Final target: scaffold-generated project base class. `data_state`/`created_time`/`updated_time`/logical-delete are backend conventions that must NOT enter generic data core. |

### 4.6 `compat/`

| Rule | Detail |
|---|---|
| May import | Legacy implementations |
| Must NOT be imported by | `core/`, `adapters/`, `security/`, `contrib/`, `data/`, `app.py` |
| Lifecycle | Governed by API deprecation policy (see migration roadmap §3) |

### 4.7 Top-level facades (`auth.py`, `tenant.py`, `__init__.py`)

| Rule | Detail |
|---|---|
| May import | `security/auth/`, `contrib/tenant/`, `adapters/sanic/`, `core/` |
| Must NOT import | `compat/`, `data/` (db proxy lazy-imports from adapters) |
| Public API | Stable, documented in `__all__` |

## 5. Legacy/Compat Rules

Legacy modules are NOT deleted based on "zero internal consumers." Deletion
follows the API deprecation policy defined in the migration roadmap (§3).

| Legacy module | Compat location | Deprecation target |
|---|---|---|
| `middleware/auth.py` | `compat/auth.py` | Per deprecation cycle |
| `middleware/sign.py` | `compat/signing.py` | Per deprecation cycle |
| `middleware/maintenance.py` | `compat/maintenance.py` | Per deprecation cycle |
| `middleware/cache.py` | `compat/cache.py` | Per deprecation cycle |
| `middleware/params.py` (`I`) | `compat/params.py` | Per deprecation cycle |
| `middleware/crypt_des.py` | `compat/crypt.py` | Per deprecation cycle |
| `middleware/crypt_params.py` (`CI`) | `compat/params.py` | Per deprecation cycle |
| `middleware/json.py` | `compat/json_encoder.py` | Per deprecation cycle |
