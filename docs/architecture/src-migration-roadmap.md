# src Migration Roadmap (Revised)

Phase: C2-R0 (first-round review remediation)
Issue: #19
Baseline: 446 passed, 1 skipped, 0 failed

## Migration Principles

1. **Constitution first (RC gate):** The development constitution (API tiers,
   machine boundary tests, decision log) must be merged before any refactor
   phase. R1-R6 are blocked until C2-RC is accepted.
2. **Small steps:** Each phase is one PR, one branch, independently reviewable
   and revertable.
3. **Public API stability:** All public facades (`lingshu.auth`, `lingshu.tenant`,
   `from lingshu import request`) remain unchanged throughout migration.
4. **Test gate:** Every phase must pass the full test suite (446+ passed) before merge.
5. **No deletion without classification:** Legacy code is moved to `compat/` with
   a `DeprecationWarning`. Deletion is governed by the deprecation cycle defined
   in §3, not by "zero consumers" or a fixed "After C3" date.
6. **Dependency narrowing:** Each phase should reduce, not increase, circular dependencies.

## Phase Dependency Graph

```
C2-RC (constitution V1 + machine boundary tests)  ← prerequisite gate
├── R1 (auth dedup + compat shims)
│   ├── R2 (sanic_adapter split + cleanup registry)
│   │   ├── R3 (tenant → contrib)
│   │   └── R4 (RoutePolicy unification)
│   ├── R5 (config modularization)
│   └── R6 (model layer decoupling + scaffold update)
```

**RC is a hard gate.** No R-phase branch may be created until C2-RC is
accepted and merged. The RC PR must include:

1. **Development constitution V1** — layer dependency rules (from
   `src-target-boundaries.md`), API tier definitions (§3 below), decision log.
2. **Machine boundary tests** — import-level tests that assert the layer rules
   programmatically (e.g. `core/` must not import `sanic`, `security/auth/`
   must not import `adapters/`). These tests run in CI and gate all future PRs.

---

## API Stability Tiers (Constitution §1)

Before any public import path is moved, renamed, or deleted, it MUST be
classified into one of these tiers. The tier governs the deprecation procedure.

| Tier | Definition | Move/Rename Procedure | Deletion Procedure |
|---|---|---|---|
| **Stable** | Documented public API: top-level facades (`lingshu.auth`, `lingshu.tenant`, `lingshu.request`, etc.), `RoutePolicy`, `Principal`, `Authenticator`. | Compat shim + `DeprecationWarning` + migration docs. Minimum 2 minor versions. | Only after deprecation cycle completes AND scaffold templates + docs are updated. |
| **Experimental** | Public but not yet stable: new auth chain APIs, new tenant resolver chain. | Compat shim recommended but not mandatory. `PendingDeprecationWarning`. | Can be removed after 1 minor version with migration docs. |
| **Internal** | `system.*` subpackages used by facades but not part of documented public API. | Free to move. No shim required if no external consumer. | Can be removed if internal audit confirms zero consumers. |
| **Deprecated** | Already marked deprecated in docs or code comments. | N/A — already in `compat/`. | Removed at next major version boundary. |

### Current classification (preliminary — finalized in C2-RC)

Authentication API is split across four entry points. Each has a distinct
tier and migration target:

| Import path | Tier | Notes |
|---|---|---|
| `from lingshu.auth import Principal, Authenticator, AuthenticatorChain, JwtBearerAuthenticator, AuthenticationOutcome, configure_authentication, get_principal, require_principal` | **Stable** | New auth API (C2.1/C2.2A). Documented, tested, public facade. These are the import paths framework scaffolds should generate. |
| `from lingshu.auth import Auth, token_required` | **Does not exist** | `lingshu.auth` does NOT export `Auth` or `token_required`. These are legacy symbols from `middleware/auth.py`. Previous classification incorrectly listed them as Stable under `lingshu.auth`. |
| `from lingshu.middleware.auth import Auth, token_required` | **Legacy** (→ Deprecated after C2-RC) | Legacy JWT auth class + decorator. Still importable today. Will be moved to `compat/auth.py` in R1 with `DeprecationWarning`. Cannot be deleted until C2-RC freezes the Deprecated tier. |
| `from lingshu.extensions.auth import Auth, token_required` | **Legacy facade** | Thin re-export of `middleware.auth`. Same lifecycle as above — becomes compat shim in R1. |
| `from app import Auth` (`app/__init__.py`) | **Project compat entry** | Project-generated re-export `from lingshu.middleware.auth import Auth`. Owned by the project scaffold. Will be updated in R6 scaffold templates to use new Stable API. |

**Non-auth classifications:**

| Import path | Tier | Notes |
|---|---|---|
| `from lingshu import request, db, config, logger` | Stable | Top-level facades |
| `from lingshu.tenant import TenantContext, TenantResolver, TenantResolverChain, ClaimTenantResolver, configure_tenant_resolution, get_tenant, require_tenant` | Stable | New tenant API (C2.2A). Documented, tested. |
| `from lingshu.router import RoutePolicy` | Stable | Public route policy |
| `from lingshu.model import Model, BaseModel` | Stable | Data model base |
| `from lingshu.system.auth.principal import Principal` | Internal | Used by facade, not documented as public |
| `from lingshu.middleware.cache import Cache` | Internal | Zero consumers in repo, but classified before any deletion |
| `from lingshu.system.auth.tenant.*` | Internal | Will move to `contrib/tenant/` |

**Rule:** No import path is deleted until it is classified. The classification
table is the output of C2-RC and lives in the constitution document.

---

## C2-R1: Auth Deduplication + Compat Shims

**Branch:** `codex/phase-c2-r1-auth-dedup`
**Depends on:** C2-RC accepted
**PR title:** `refactor(c2-r1): consolidate auth entry points and add compat shims`

### Scope
- Move `middleware/auth.py` to `compat/auth.py` (keep `Auth`/`token_required`
  as shims with `DeprecationWarning`).
- Update `extensions/auth.py` to re-export from `compat/auth.py`.
- Move `middleware/cache.py` to `compat/cache.py` with `DeprecationWarning`
  (classified as Internal — see §3 — but gets a shim because it was importable).
- Move `middleware/__init__.py` `init_app` stub to `compat/` with shim
  (classified as Internal, zero callers confirmed in audit).
- Move unused functions in `middleware/utils.py` (`filter_zjh`, `get_nonce_str`,
  `get_server_ip`, `get_ip`, `exists_path`) to `compat/utils.py`.
- Keep `middleware/utils.py` legacy `json_response` with `DeprecationWarning`.

### Forbidden
- No direct deletion. Everything gets a compat shim.
- No changes to `system/auth/*`.
- No changes to `system/auth/tenant/*`.
- No changes to `system/sanic_adapter.py`.
- No changes to any test other than updating import paths.

### Public API compat
- `from lingshu.middleware.auth import Auth` → works, emits `DeprecationWarning`.
- `from lingshu.extensions.auth import Auth` → works (re-export).
- `from lingshu.middleware.cache import Cache` → works, emits `DeprecationWarning`.
- `from lingshu.middleware.utils import json_response` → works, emits `DeprecationWarning`.

### Test contract
- `tests/test_c2_auth.py`: 111 passed (no regression).
- `tests/test_c2_tenant.py`: 127 passed (no regression).
- `tests/test_security_extensions.py`: Updated — cache assertion now checks
  that import succeeds AND emits DeprecationWarning.
- New test: assert all compat shims emit `DeprecationWarning`.
- Full suite: ≥446 passed (adjusted for new compat tests).

### Rollback
- Pure code movement + shim addition. Revert the PR to restore.

---

## C2-R2: Sanic Adapter Split + App-Scoped Cleanup Registry

**Branch:** `codex/phase-c2-r2-adapter-split`
**Depends on:** C2-R1 accepted
**PR title:** `refactor(c2-r2): split sanic_adapter and introduce app-scoped cleanup registry`

### Scope
- Split `system/sanic_adapter.py` (284 LOC) into:
  - `adapters/sanic/context_middleware.py` — `install_context_middleware` + request lifecycle
  - `adapters/sanic/resource_registry.py` — `set_resource`/`get_resource`/`get_app_config`/etc.
  - `adapters/sanic/cleanup_registry.py` — `AppCleanupRegistry` (per `src-target-boundaries.md` §2)
  - `adapters/sanic/finalize.py` — `finalize_request_context` (uses cleanup registry)
  - `adapters/sanic/routing.py` — `_route_policy_for_request` + `_request_route_name`
- Implement `AppCleanupRegistry` as designed in target-boundaries §2.2–§2.3:
  - Per-app instance on `app.ctx.cleanup_registry`.
  - Hook registration via `registry.register(hook_id, fn, order=...)`.
  - **Per-hook** completion tracking via `_lingshu_completed_hooks` set on
    `request.ctx`. A hook is marked complete only AFTER it runs (success or
    exception). No pre-set `_lingshu_cleanup_done` flag.
  - Same `hook_id` + same `fn` → idempotent no-op.
  - Same `hook_id` + different `fn` → `CleanupConfigError` at install time.
  - `CancelledError` always propagated; necessary cleanup from
    previously-completed hooks is already applied.
  - Deadline exhausted does NOT skip necessary context cleanup.
  - Other exceptions logged at WARNING, aggregated, NOT swallowed.
  - `except Exception: pass` is FORBIDDEN.
- Refactor `_reset_principal_binding` and `_reset_tenant_binding` into
  registered hooks (auth and tenant modules register their own cleanup during
  middleware installation).
- Extract `_deep_freeze` into `core/types.py`.
- Extract `Binding` base protocol into `core/types.py`.
- Move `system/registry.py` and `system/resources.py` (3-line re-export shims)
  into the new `adapters/sanic/resource_registry.py`.

### Forbidden
- No changes to middleware installation order.
- No changes to `system/policy.py` compilation logic.
- No changes to any Stable public API.
- No changes to `system/tasks.py`.
- NO module-level global `_cleanup_hooks` (rejected pattern per target-boundaries §2.1).
- NO `except Exception: pass` in cleanup (rejected pattern per target-boundaries §2.3).

### Public API compat
- `from lingshu.system.sanic_adapter import *` → works (compat re-export from
  new locations). Classified as Internal.
- `from lingshu.system import sanic_adapter` → works.

### Test contract
- All existing tests pass unchanged.
- New tests for `AppCleanupRegistry`:
  - Verify auth/tenant cleanup hooks are called on normal/exception/timeout/cancel paths.
  - Verify `CancelledError` is propagated (not swallowed).
  - Verify other exceptions are logged and aggregated (not swallowed).
  - Verify per-hook idempotency: `run_all()` called twice only runs each hook once.
  - Verify per-app isolation: two registries do not interfere.
  - Verify hook ordering: hooks run in ascending `order`, then registration order.
  - Verify conflicting registration (same `hook_id`, different `fn`) raises `CleanupConfigError`.
  - Verify duplicate registration (same `hook_id`, same `fn`) is idempotent no-op.
  - Verify deadline exhaustion does NOT skip necessary context cleanup.
- Machine boundary test (from RC): assert `adapters/sanic/` may import Sanic,
  `core/` may not.
- Full suite: ≥446 passed.

### Rollback
- Revert the PR. The split is mechanical — no logic changes.

---

## C2-R3: Tenant Module Relocation

**Branch:** `codex/phase-c2-r3-tenant-contrib`
**Depends on:** C2-R2 accepted (cleanup registry must exist)
**PR title:** `refactor(c2-r3): move tenant from auth internal to contrib module`

### Scope
- Move `system/auth/tenant/` directory to `contrib/tenant/`.
- Update all import paths:
  - `system/auth/tenant/context.py` → `contrib/tenant/context.py`
  - `system/auth/tenant/result.py` → `contrib/tenant/result.py`
  - `system/auth/tenant/binding.py` → `contrib/tenant/binding.py`
  - `system/auth/tenant/resolver.py` → `contrib/tenant/resolver.py`
  - `system/auth/tenant/claim_resolver.py` → `contrib/tenant/claim_resolver.py`
  - `system/auth/tenant/stub_resolver.py` → `contrib/tenant/stub_resolver.py`
- Update `lingshu.tenant` facade to import from new location.
- Update `adapters/sanic/finalize.py` to use the registered cleanup hook
  (no longer hardcodes `lingshu_tenant_binding`).
- Update test imports (tests import from `lingshu.tenant`, not
  `lingshu.system.auth.tenant`).

### Forbidden
- No logic changes to any tenant resolver, middleware, or binding.
- No changes to `system/auth/*` (auth stays as-is, just loses the tenant/ subdirectory).
- No changes to public API (`lingshu.tenant.*` unchanged — Stable tier).
- `contrib/tenant/` must NOT import `adapters/` or Sanic (domain purity).

### Public API compat
- `from lingshu.tenant import *` → unchanged (Stable).
- `from lingshu.system.auth.tenant import *` → compat re-export shim at old
  location, classified as Internal, emits `DeprecationWarning`.

### Test contract
- `tests/test_c2_tenant.py`: 127 passed (only import paths change, if any).
- New machine boundary test: `contrib/tenant/` must not import Sanic.
- Full suite: ≥446 passed.

### Rollback
- Move directory back. No logic changes to revert.

---

## C2-R4: RoutePolicy Unification

**Branch:** `codex/phase-c2-r4-policy-unification`
**Depends on:** C2-R2 accepted (policy compiler in adapters)
**PR title:** `refactor(c2-r4): unify RoutePolicy public and internal definitions`

### Scope
- Add `signing_required` field to `RoutePolicyDefinition` (currently missing —
  exists only on legacy `RoutePolicy`).
- Make `RoutePolicy` (in `router.py`) a thin alias/subclass of `RoutePolicyDefinition`.
- Remove `from_legacy()` conversion path (both definitions become the same type).
- Update `RoutePolicyCompiler._normalize_definition()` to handle unified type directly.

### Forbidden
- No changes to policy compilation/wrapping logic.
- No changes to deadline/timeout behavior.
- No changes to auth/tenant middleware.

### Public API compat
- `RoutePolicy(auth_required=True, signing_required=False, tenant_required=False)` →
  unchanged signature (Stable).
- `RoutePolicyDefinition(...)` → gains `signing_required` field (additive).

### Test contract
- `tests/test_c2_auth.py`: 111 passed.
- `tests/test_c2_tenant.py`: 127 passed.
- New tests for `RoutePolicyDefinition.signing_required` compilation.
- Full suite: ≥446 passed.

### Rollback
- Revert the PR. The unification is additive.

---

## C2-R5: Configuration Modularization

**Branch:** `codex/phase-c2-r5-config-modular`
**Depends on:** C2-R1 accepted
**PR title:** `refactor(c2-r5): split AppConfig into capability-scoped config objects`

### Scope
- Split `AppConfig` (35+ fields) into:
  - `AppMetaConfig` — app_name, project_name, host, port, workers, debug, language
  - `AuthConfig` — enable_auth, auth_secret, auth_app, auth_expire, auth_white_ip_list
  - `SigningConfig` — enable_signing, signing_secret
  - `DatabaseConfig` — enabled_databases, mysql_enabled, etc. + connection dicts
  - `CORSConfig` — cors_enabled, cors_origins, cors_allow_methods, etc.
  - `LoggingConfig` — log_to_file, log_level, log_path, etc.
  - `CryptoConfig` — crypt_response_enabled, crypt_response_secret, crypt_params_secret
- `AppConfig` becomes a frozen container holding these sub-configs.
- Backward compat: `app_config.auth_secret` delegates to `app_config.auth.secret`.

### Forbidden
- No changes to `.env` file format.
- No changes to environment variable names.
- No new dependencies.

### Test contract
- All existing tests pass.
- New tests for sub-config access patterns.
- Full suite: ≥446 passed.

### Rollback
- Revert. The split is structural, not behavioral.

---

## C2-R6: Model Layer Decoupling + Scaffold Update

**Branch:** `codex/phase-c2-r6-model-decouple`
**Depends on:** C2-R1 accepted
**PR title:** `refactor(c2-r6): decouple model layer and update scaffold templates`

### Scope
- Refactor `Model` (model/model.py) to accept `db` and `redis` as parameters
  instead of importing `lingshu.db` global.
- Refactor `BusinessModel` (model/business.py) to accept `request` as parameter
  instead of importing `lingshu.request` global.
- Keep backward-compat: if `db`/`redis`/`request` not passed, fall back to globals
  with `DeprecationWarning`.
- Move `model/` directory to `data/model/`.

### BusinessModel decision

`BusinessModel` binds a model to the request lifecycle (auth principal, tenant
context, request-scoped DB connection). This is a **project service-layer
pattern**, not a generic data-core type. The decision is finalized as:

1. **BusinessModel does NOT belong in the generic data core.** It couples to
   request lifecycle, auth principal, and tenant context — concerns that are
   outside the scope of `data/model/`.
2. **R6 does NOT move BusinessModel into `data/model/`.** The old path
   (`model/business.py` → `data/model/business.py`) is preserved temporarily
   for backward compatibility.
3. **Old import paths are kept with `DeprecationWarning`.** Projects that
   import `from lingshu.model import BusinessModel` continue to work during
   the deprecation cycle.
4. **R6 only decouples BusinessModel from global proxies.** The constructor
   gains optional `request`, `db`, `redis` parameters. When not passed, it
   falls back to globals with `DeprecationWarning`. This is the ONLY change
   to BusinessModel in R6.
5. **Final target: scaffold-generated project service base class.** In a
   future phase after R6, `BusinessModel` will move to scaffold-generated
   code (`business_model.py.j2`) or to a separate optional module
   (`contrib/business/`). R6 does not execute this move.
6. **`data_state`, `created_time`, `updated_time`, logical-delete fields:**
   These are backend web-service conventions, NOT generic data-core concerns.
   They MUST NOT enter the generic `data/model/` core. They stay in the
   current legacy `model/` code for backward compat during the deprecation
   cycle. The scaffold template (`business_model.py.j2`) will own these
   conventions in the target state.

### Scaffold template update (REQUIRED, not forbidden)

Previous roadmap forbade scaffold changes. This is corrected: **scaffold
templates MUST generate code using the new stable import paths.**

- Update `src/lingshu/scaffold/*.j2` templates to generate imports using:
  - `from lingshu import request, db` (Stable facade — unchanged)
  - `from lingshu.model import Model` (Stable — unchanged path)
  - `from lingshu.auth import Principal, AuthenticatorChain, JwtBearerAuthenticator, configure_authentication` (Stable facade — new auth API, NOT the legacy `Auth`/`token_required`)
- Remove any template references to `lingshu.system.*` or `lingshu.middleware.*`.
- Add a **scaffold smoke test**: generate a project from templates, assert all
  generated imports resolve without error.

### Forbidden
- No changes to SQL generation logic.
- No changes to cache behavior.
- NO scaffold template that imports `lingshu.system.*` (machine boundary test catches this).

### Test contract
- All existing tests pass.
- New tests for dependency-injected model access.
- New scaffold smoke test (generate project → import all modules).
- Full suite: ≥446 passed.

### Rollback
- Revert. The changes are additive (parameters have defaults).

---

## Deprecation and Deletion Cycle

### Compat shim lifecycle

All compat shims added in R1–R6 follow this lifecycle:

1. **Introduction (R-phase):** Module moved to `compat/`. Old import path emits
   `DeprecationWarning`. Migration documented in scaffold README.
2. **Observation (≥2 minor versions):** CI monitors for compat shim usage.
   If zero external consumers after 2 minor versions, proceed to removal.
3. **Removal (major version):** Compat shim deleted. Removal announced in
   changelog with migration guide.

### Deletion is NOT "After C3"

The previous roadmap stated "Compat shims are removed in a cleanup PR after C3."
This is corrected: **deletion is governed by the deprecation cycle defined above,
not by a fixed phase boundary.** A compat shim may survive past C3 if it still
has consumers. Conversely, it may be removed before C3 if the audit confirms
zero consumers AND it is classified as Internal or Deprecated.

### Decision authority

| Classification | Deletion authority |
|---|---|
| Stable | Requires major version bump + migration guide + scaffold update |
| Experimental | Minor version bump + migration docs |
| Internal | Confirmed zero consumers in audit → may delete in any R-phase |
| Deprecated | Next major version boundary |

---

## C2.2B Resume Condition

C2.2B (and later C3) may begin only after:
1. C2-RC is accepted and merged.
2. C2-R1 through C2-R4 are merged and accepted.
3. C2-R5 and C2-R6 may proceed in parallel with C2.2B if they don't touch
   auth/tenant/middleware.
4. The lazy import cycle (`system.auth.middleware → exception`) is resolved (R2).
5. `sanic_adapter.py` is split into `adapters/sanic/` (R2).
6. Tenant module is relocated to `contrib/tenant/` (R3).
7. Scaffold templates generate new stable imports (R6).

These conditions ensure C2.2B builds on a clean layer structure.

## Test Baseline

| Checkpoint | Minimum |
|---|---|
| After C2-RC | 446 passed + new machine boundary tests passing |
| After each R phase | 446 passed, 1 skipped, 0 failed + new phase-specific tests |
| After all R phases | ≥446 passed + machine boundary tests + scaffold smoke test |
