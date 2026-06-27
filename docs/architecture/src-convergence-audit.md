# src Convergence Audit (Revised)

Phase: C2-R0 (first-round review remediation)
Issue: #19
Branch: research/c2-src-convergence
Code baseline: commit `2fc6e6b` (main, post PR #18 merge)
Test baseline: 446 passed, 1 skipped, 0 failed

> Revision notes: This document corrects factual errors from the initial
> audit (commit `198194f`) identified in the first-round architecture review.
> All line counts and import locations are verified against `2fc6e6b`.

## 1. Complete Directory Inventory

### 1.1 Framework package: `src/lingshu/`

```
src/lingshu/
├── __init__.py                  22 LOC   Facade: abort, language, proxies
├── app.py                       88 LOC   Application factory create_app()
├── auth.py                      75 LOC   Public auth facade (re-exports)
├── config.py                   258 LOC   AppConfig + load_config() + facade
├── controller.py                19 LOC   Request payload helpers
├── error_codes.py              358 LOC   Error-code catalog parsing/validation
├── exception.py                 56 LOC   APIException + get_error_message
├── helper.py                    20 LOC   write_verify_log + exists_path
├── i18n.py                      32 LOC   sanic_babel setup + ini i18n parser
├── lifecycle.py                 59 LOC   Wiring: registers system.lifecycle onto app
├── logging.py                   64 LOC   setup_logging() + request-context filter
├── middleware_registry.py       48 LOC   CORS + X-Request-ID middleware
├── response.py                  10 LOC   json_response() unified builder
├── router.py                    20 LOC   RoutePolicy + blueprint registration
├── runtime.py                    7 LOC   run_app() entry point
├── tenant.py                    54 LOC   Public tenant facade (re-exports)
├── versioning.py                16 LOC   API version parsing from URL path
│
├── cli/
│   ├── __init__.py               1 LOC
│   ├── main.py                 289 LOC   CLI entry: init, add, make, check
│   └── project.py              494 LOC   Scaffold engine + project linter (AST)
│
├── database/
│   ├── __init__.py               4 LOC   Re-exports MongoDB, MySQLDatabase, RedisManager
│   ├── dependencies.py          25 LOC   Optional driver import guard
│   ├── mongo.py                 90 LOC   Motor async MongoDB wrapper
│   ├── mysql.py                150 LOC   aiomysql wrapper with read-splitting
│   └── redis.py                322 LOC   Redis async client with Sentinel support
│
├── extensions/
│   ├── __init__.py               0 LOC
│   ├── auth.py                   4 LOC   Re-export middleware.auth (LEGACY)
│   ├── cache.py                  4 LOC   Re-export middleware.cache (LEGACY)
│   ├── i18n.py                   4 LOC   Re-export lingshu.i18n (UNUSED)
│   ├── maintenance.py            4 LOC   Re-export middleware.maintenance (LEGACY)
│   ├── mongo.py                 19 LOC   MongoDB lifecycle hook (ACTIVE)
│   ├── mysql.py                 19 LOC   MySQL lifecycle hook (ACTIVE)
│   ├── redis.py                 18 LOC   Redis lifecycle hook (ACTIVE)
│   ├── registry.py              44 LOC   Extension orchestrator (ACTIVE)
│   └── signing.py                4 LOC   Re-export middleware.sign (LEGACY)
│
├── language/                             Framework built-in error-code messages
│   ├── zh-CN/ERROR/
│   │   ├── auth.ini              Tenant/auth error messages (990100-990124)
│   │   ├── db.ini                Database error messages (990200-990299)
│   │   ├── param.ini             Parameter validation messages (991100-991199)
│   │   └── system.ini            System error messages (990000-990099)
│   └── en-US/ERROR/
│       ├── auth.ini
│       ├── db.ini
│       ├── param.ini
│       └── system.ini
│
├── middleware/
│   ├── __init__.py               8 LOC   init_app stub (no callers)
│   ├── auth.py                 161 LOC   Legacy JWT auth (Auth, token_required)
│   ├── cache.py                114 LOC   Filesystem cache (no active consumers)
│   ├── crypt_des.py             49 LOC   DES-CBC encryption (legacy active)
│   ├── crypt_params.py          97 LOC   Encrypted param accessor CI (legacy active)
│   ├── json.py                  13 LOC   CustomJSONEncoder (active)
│   ├── maintenance.py           61 LOC   Maintenance decorator (legacy)
│   ├── params.py               117 LOC   Param accessor I() (legacy active)
│   ├── sign.py                  69 LOC   Sign verification decorator (legacy)
│   └── utils.py                101 LOC   Mixed utilities (md5, ip, legacy json_response)
│
├── model/
│   ├── __init__.py               4 LOC   Re-exports BaseModel, BusinessModel, Model
│   ├── base.py                 378 LOC   Active-record ORM engine (SQL builder + cache)
│   ├── business.py              30 LOC   Non-table business logic mixin (uses globals)
│   └── model.py                214 LOC   Instance-based compat Model (soft-delete, timestamps)
│
├── resources/                           Framework built-in error-code module registry
│   └── error_codes/
│       └── modules.ini                   Maps code ranges to module names
│
├── scaffold/                            Jinja2 templates for project scaffolding
│   ├── business_model.py.j2
│   ├── controller.py.j2
│   ├── docker-compose.yml.j2
│   ├── docs.md.j2
│   ├── env.example.j2
│   ├── pyproject.toml.j2
│   ├── README.md.j2
│   ├── table_model.py.j2
│   └── view.html.j2
│
├── system/
│   ├── __init__.py               1 LOC
│   ├── context.py               97 LOC   ContextVar management (app/request/user)
│   ├── errors.py                11 LOC   Framework exception hierarchy
│   ├── execution.py            119 LOC   RequestExecutionContext (deadline, cancel)
│   ├── lifecycle.py            231 LOC   Lifecycle state machine + health routes
│   ├── policy.py               198 LOC   RoutePolicyDefinition + compiler
│   ├── proxies.py              105 LOC   Global proxies (logger, config, app, request, db)
│   ├── registry.py               3 LOC   Re-export sanic_adapter resource functions
│   ├── resources.py              3 LOC   Re-export db proxy
│   ├── sanic_adapter.py        284 LOC   Sanic adapter (context, finalize, middleware)
│   ├── tasks.py                233 LOC   Background task registry + lifecycle
│   └── auth/
│       ├── __init__.py          44 LOC   Internal auth module aggregation
│       ├── authenticator.py     88 LOC   Authenticator Protocol + Chain
│       ├── context.py           52 LOC   Principal ContextVar binding
│       ├── jwt_bearer.py       157 LOC   JWT Bearer authenticator (PyJWT)
│       ├── jwt_test_helpers.py  52 LOC   Test-only JWT token generation
│       ├── middleware.py       135 LOC   Auth fail-closed middleware
│       ├── principal.py         78 LOC   Principal frozen dataclass
│       ├── result.py           124 LOC   AuthResult enum + AuthenticationOutcome
│       ├── stub_authenticator.py 73 LOC  Test stub
│       └── tenant/
│           ├── __init__.py       0 LOC
│           ├── binding.py       48 LOC   TenantContext ContextVar binding
│           ├── claim_resolver.py 119 LOC Claim-based resolver
│           ├── context.py       63 LOC   TenantContext frozen dataclass
│           ├── middleware.py   120 LOC   Tenant fail-closed middleware
│           ├── resolver.py      78 LOC   TenantResolver Protocol + Chain
│           ├── result.py        90 LOC   TenantResolutionResult + Outcome
│           └── stub_resolver.py 53 LOC   Test stub
│
└── view/
    └── __init__.py               1 LOC   Placeholder package
```

### 1.2 Project code: `app/` and `config/`

```
app/
├── __init__.py                           Re-exports legacy public API (Auth, I, CI, etc.)
├── bootstrap.py                          get_extension_modules() — DB lifecycle wiring
├── common.py                             Project shared utilities
├── event.py                              Event definitions
├── helper.py                             Project-level helpers
├── route.py                              Blueprint registration
├── .gitignore
├── controller/                           Project controllers (health check)
├── language/                             Project error-code overrides + user module
│   ├── .gitignore
│   ├── modules.ini                       Project module registry (code ranges)
│   ├── zh-CN/ERROR/
│   │   ├── auth.ini                      Overrides/augments framework auth.ini
│   │   ├── db.ini
│   │   ├── param.ini
│   │   ├── system.ini
│   │   └── user.ini                      Project-specific error codes (110000-119999)
│   └── en-US/ERROR/
│       ├── auth.ini
│       ├── db.ini
│       ├── param.ini
│       ├── system.ini
│       └── user.ini
└── v1/                                   Versioned API directory (created by CLI)

config/
└── defaults.py                           Project-level default settings
```

**`app/resources/` does not exist.** Project resources are not currently a concept.

### 1.3 Language double-source analysis

The framework ships built-in error-code messages in `src/lingshu/language/`.
The project can override or augment these in `app/language/`.

**Loading order** (from `exception.py` → `error_codes.py`):
1. `app/<version>/language/` — version-specific overrides (if version directory exists)
2. `app/language/` — project-level overrides
3. `src/lingshu/language/` — framework built-in defaults

**Overlap risk:** `auth.ini`, `db.ini`, `param.ini`, `system.ini` exist in
BOTH locations. When a new error code is added to the framework (e.g.
990120-990124 for tenant), the framework `.ini` must be updated, but projects
that have their own `app/language/*/ERROR/auth.ini` will NOT see the new
messages unless they also update their copy.

**Current mitigation:** `get_error_message()` falls back to framework defaults
when the project file lacks a specific code. But the error-code *catalog*
(`build_error_code_index`) scans both roots, so the index is complete — only
individual message resolution may be stale in project copies.

### 1.4 Resources analysis

`src/lingshu/resources/error_codes/modules.ini` defines the canonical module
range registry:
```ini
[Modules]
100000-109999 = language
990000-990099 = system
990100-990199 = auth
990200-990299 = db
991100-991199 = param
```

`app/language/modules.ini` adds project-specific ranges (e.g. `110000-119999 = user`).
These are merged at scan time. No `app/resources/` directory exists — resources
are framework-only.

## 2. Framework/Project Ownership Matrix

| Path | Owner | Modifiable by project? | Ships with framework? | Upgrade risk |
|---|---|---|---|---|
| `src/lingshu/**` | Framework maintainers | **No** — must use framework Issue/PR | Yes | Framework upgrade overwrites |
| `src/lingshu/language/**` | Framework maintainers | **Override only** via `app/language/` | Yes | New framework codes require project copy sync |
| `src/lingshu/resources/**` | Framework maintainers | **No** — project uses `app/language/modules.ini` | Yes | — |
| `src/lingshu/scaffold/**` | Framework maintainers | **No** — templates are framework source | Yes | Template changes affect new projects only |
| `app/**` | Project developers | **Yes** | No (generated by scaffold) | — |
| `app/language/**` | Project developers | **Yes** — can override framework messages | No | Framework new codes need manual sync |
| `app/bootstrap.py` | Project developers | **Yes** — wires extensions | No (generated, then modified) | Scaffold update may require manual merge |
| `config/defaults.py` | Project developers | **Yes** — project settings | No (generated) | — |
| `controller.py` (framework) | Framework | **No** | Yes | — |
| `helper.py` (framework) | Framework | **No** | Yes | — |
| `view/` (framework) | Framework | **No** — placeholder | Yes | — |
| Scaffold-generated files | **Project** after generation | **Yes** — owned by project post-generation | No | Framework upgrade does NOT touch generated files |

**Key principle:** Business developers must never modify `site-packages/src/lingshu/`
to implement business requirements. All business customization goes in `app/`
or `config/`.

## 3. Sanic Dependency Analysis

### 3.1 Direct Sanic imports in `src/lingshu/` (verified)

| File | Line | Statement |
|---|---|---|
| `app.py` | 6 | `from sanic import Sanic` |
| `app.py` | 7 | `from sanic.exceptions import SanicException` |
| `response.py` | 1 | `from sanic import response` |
| `middleware_registry.py` | 4 | `from sanic import response` |
| `middleware/auth.py` | 8 | `from sanic import Request` |
| `middleware/cache.py` | 12 | `from sanic.request import Request` |
| `middleware/crypt_des.py` | 10 | `from sanic.request import Request` |
| `middleware/crypt_params.py` | 7 | `from sanic.request import Request` |
| `middleware/maintenance.py` | 6 | `from sanic import response` |
| `middleware/params.py` | 6 | `from sanic.request import Request` |
| `middleware/utils.py` | 9 | `from sanic.request import Request` |
| `middleware/utils.py` | 10 | `from sanic.response import json` |
| `i18n.py` | 7 | `from sanic_babel import Babel` |

**Previous audit incorrectly claimed "no file directly import sanic."** This
is false. The framework has 13 direct Sanic/Sanic-subpackage imports across
9 files. The correct boundary principle is:

- **`core/` must NOT import Sanic** — this is a hard architectural constraint.
- **`adapters/sanic/` MAY import Sanic** — this is the Sanic integration layer;
  direct imports are expected and correct.
- **Middleware and application modules** (legacy `middleware/`, `app.py`,
  `response.py`) currently import Sanic directly — this is acceptable for
  application-level code but should migrate into `adapters/sanic/` during
  refactoring phases.

## 4. Dependency Graph Evidence

### 4.1 Static module-level edges (top-level package)

Computed by AST scanning all `.py` files at commit `2fc6e6b`. Only
`import` and `from ... import` at module top level (indentation 0).

| Package | Static dependencies (lingshu.*) |
|---|---|
| `__init__` | exception, system |
| `app` | config, exception, lifecycle, logging, middleware_registry, response, router, runtime, system |
| `auth` | system |
| `cli` | cli(self), error_codes, versioning |
| `config` | error_codes |
| `controller` | exception |
| `database` | database(self), helper |
| `error_codes` | (none) |
| `exception` | error_codes, system, versioning |
| `extensions` | database, i18n, middleware, system |
| `helper` | middleware, system |
| `i18n` | error_codes |
| `lifecycle` | extensions, system |
| `logging` | system |
| `middleware` | exception, middleware(self), system |
| `middleware_registry` | system |
| `model` | middleware, model(self), system |
| `response` | (none) |
| `router` | system |
| `runtime` | system |
| `system` | exception, response, system(self) |
| `tenant` | system |
| `versioning` | (none) |
| `view` | (none) |

### 4.2 Function-level lazy edges (29 deferred imports)

These are `from lingshu.*` or `import lingshu.*` statements appearing inside
function/method bodies (not at module top level). They break potential import
cycles.

| # | File:Line | Deferred import | Containing function |
|---|---|---|---|
| 1 | `__init__.py:8` | `lingshu.exception.get_error_message` | `LanguageFacade.get()` |
| 2 | `app.py:59` | `lingshu.system.auth.middleware.install_authentication_middleware` | `create_app()` |
| 3 | `app.py:62` | `lingshu.system.auth.tenant.middleware.install_tenant_middleware` | `create_app()` |
| 4 | `app.py:102` | `lingshu.system.context.get_current_app` | exception handler closure |
| 5 | `auth.py:67` | `lingshu.system.auth.middleware.set_authenticator_chain` | `configure_authentication()` |
| 6 | `auth.py:78` | `lingshu.system.execution.current_execution_context` | `get_principal()` |
| 7 | `auth.py:80` | `lingshu.system.auth.context.current_principal` | `get_principal()` |
| 8 | `auth.py:89` | `lingshu.system.execution.current_execution_context` | `require_principal()` |
| 9 | `auth.py:91` | `lingshu.system.auth.context.require_principal` | `require_principal()` |
| 10 | `config.py:282` | `lingshu.system.context.get_current_app` | `_ConfigModule._facade_config()` |
| 11 | `config.py:283` | `lingshu.system.sanic_adapter.get_app_config` | `_ConfigModule._facade_config()` |
| 12 | `tenant.py:42` | `lingshu.system.auth.tenant.middleware.set_tenant_resolver_chain` | `configure_tenant_resolution()` |
| 13 | `tenant.py:53` | `lingshu.system.execution.current_execution_context` | `get_tenant()` |
| 14 | `tenant.py:55` | `lingshu.system.auth.tenant.binding.current_tenant` | `get_tenant()` |
| 15 | `tenant.py:64` | `lingshu.system.execution.current_execution_context` | `require_tenant()` |
| 16 | `tenant.py:66` | `lingshu.system.auth.tenant.binding.require_tenant` | `require_tenant()` |
| 17 | `runtime.py:5` | `lingshu.system.sanic_adapter.get_app_config` | `run_app()` |
| 18 | `middleware/crypt_params.py:46` | `lingshu.exception.get_error_message` | except block in method |
| 19 | `extensions/mysql.py:8` | `lingshu.database.mysql.MySQLDatabase` | `setup()` |
| 20 | `extensions/mongo.py:8` | `lingshu.database.mongo.MongoDB` | `setup()` |
| 21 | `system/lifecycle.py:178` | `lingshu.system.policy.RoutePolicyDefinition` | `_mark_health_policy()` |
| 22 | `system/policy.py:174` | `lingshu.system.sanic_adapter.finalize_request_context` | `deadline_wrapper()` |
| 23 | `system/sanic_adapter.py:177` | `lingshu.system.tasks._summarize_exception` | `finalize_request_context()` except |
| 24 | `system/proxies.py:107` | `lingshu.system.auth.context.current_principal` | `RequestProxy.principal` |
| 25 | `system/proxies.py:114` | `lingshu.system.auth.tenant.binding.current_tenant` | `RequestProxy.tenant` |
| 26 | `system/auth/middleware.py:84` | `lingshu.exception.get_error_message` | middleware handler |
| 27 | `system/auth/middleware.py:170` | `lingshu.system.sanic_adapter.finalize_request_context` | middleware handler |
| 28 | `system/auth/tenant/middleware.py:67` | `lingshu.exception.get_error_message` | middleware handler |
| 29 | `system/auth/tenant/middleware.py:113` | `lingshu.system.auth.context.current_principal` | middleware handler |
| 30 | `system/auth/tenant/middleware.py:153` | `lingshu.system.sanic_adapter.finalize_request_context` | middleware handler |

### 4.3 Circular dependency: precise analysis

**Claim:** `exception <-> system` is a circular dependency.

**Verification:** Trace the exact static import chain:

```
exception.py (line 6):  from lingshu.system.context import current_app, current_request
exception.py (line 7):  from lingshu.system.sanic_adapter import get_app_config
```

Both are **static module-level** imports. Now check whether any `system/*.py`
file statically imports `lingshu.exception`:

- `system/sanic_adapter.py`: No import of `lingshu.exception` at any level.
- `system/lifecycle.py`: No import of `lingshu.exception` at any level.
- `system/policy.py`: No import of `lingshu.exception` at any level.
- `system/context.py`: No import of `lingshu.exception` at any level.
- `system/execution.py`: No import of `lingshu.exception` at any level.

**Conclusion:** There is **no static circular dependency** between `exception`
and `system`. The dependency is one-directional at the static level:

```
exception --> system.context (static)
exception --> system.sanic_adapter (static)
```

No system module imports back into exception.

**However**, there IS a **potential lazy cycle**:
- `system/auth/middleware.py:84` → lazy import `lingshu.exception.get_error_message`
- `system/auth/tenant/middleware.py:67` → lazy import `lingshu.exception.get_error_message`

Since `exception.py` statically imports `system.sanic_adapter`, and the auth
middleware modules are under `system/`, the import chain
`exception → system.sanic_adapter → (same package) → system.auth.middleware → exception`
would cycle if the lazy imports were promoted to static. The lazy imports
correctly break this potential cycle.

**Classification:**
- Static cycles: **none** between exception and system.
- Lazy/potential cycles: `system.auth.middleware → exception` (lazy, items 26-30 above).
- Conceptual coupling: `system.sanic_adapter` knows about auth/tenant binding
  attribute names (`lingshu_principal_binding`, `lingshu_tenant_binding`) — this
  is a **conceptual coupling**, not an import cycle, but it creates a hidden
  contract between adapter and security layers.

### 4.4 `_deep_freeze` / `_freeze_value` — 4 definitions

| # | File:Line | Function name |
|---|---|---|
| 1 | `config.py:268` | `_freeze_value` |
| 2 | `system/proxies.py:12` | `_freeze_value` |
| 3 | `system/auth/principal.py:8` | `_deep_freeze` |
| 4 | `system/auth/tenant/context.py:8` | `_deep_freeze` |

### 4.5 Binding pattern — 4 classes

| # | File:Line | Class name |
|---|---|---|
| 1 | `system/context.py:18` | `_ContextTokens` |
| 2 | `system/execution.py:27` | `_ExecutionBinding` |
| 3 | `system/auth/context.py:16` | `_PrincipalBinding` |
| 4 | `system/auth/tenant/binding.py:16` | `_TenantBinding` |

## 5. New vs Legacy Overlap Matrix

| Concern | New (system/) | Legacy (middleware/ + extensions/) | Status |
|---|---|---|---|
| Authentication | `system.auth.*` | `middleware/auth.py` (Auth, token_required) | Legacy re-exported via `extensions/auth.py` |
| Signing | `system.policy` (no signing_required field) | `middleware/sign.py` | Legacy re-exported via `extensions/signing.py` |
| Maintenance | `system.lifecycle` | `middleware/maintenance.py` | Legacy re-exported via `extensions/maintenance.py` |
| Caching | (none) | `middleware/cache.py` | No active consumers in repo; external usage unknown |
| Response | `response.json_response()` | `middleware/utils.json_response()` | Signature collision (different parameter lists) |
| RoutePolicy | `system.policy.RoutePolicyDefinition` (7 fields) | `router.RoutePolicy` (4 fields) | `from_legacy()` bridges; `signing_required` missing in new |

## 6. Hot Files (exact LOC, top 10)

| Rank | File | LOC | Concerns |
|---|---|---|---|
| 1 | `cli/project.py` | 494 | Scaffold engine + AST linter |
| 2 | `model/base.py` | 378 | SQL builder + cache + active-record |
| 3 | `error_codes.py` | 358 | Catalog parser + validator |
| 4 | `database/redis.py` | 322 | Redis client (Sentinel + direct) |
| 5 | `config.py` | 258 | AppConfig + env parsing + module facade |
| 6 | `cli/main.py` | 289 | CLI argument dispatch |
| 7 | `system/tasks.py` | 233 | Task registry + sanitization |
| 8 | `system/lifecycle.py` | 231 | Lifecycle + health + shutdown |
| 9 | `system/policy.py` | 198 | Route policy compiler |
| 10 | `system/auth/jwt_bearer.py` | 157 | JWT authenticator |

`sanic_adapter.py` is 284 LOC — rank 11, not the largest file, but it has the
highest **responsibility density** (20+ functions across 6 concern areas).

## 7. Technical Debt Priority

| Priority | Issue | Risk | Phase |
|---|---|---|---|
| P0 | `sanic_adapter.py` has 6 concern areas in 284 LOC | Hard to test/extend | C2-R2 |
| P0 | Adapter hardcodes auth/tenant binding attribute names | Conceptual coupling, hidden contract | C2-R3 |
| P1 | Legacy auth (`middleware/auth.py`) shadows new auth | Dual auth paths | C2-R1 |
| P1 | `RoutePolicy` dual model, `signing_required` lost | Signing unenforceable in new model | C2-R4 |
| P1 | `BusinessModel` and `Model` depend on global proxies | Untestable without request context | C2-R6 |
| P2 | `_deep_freeze` / `_freeze_value` in 4 locations | Maintenance burden | C2-R2 |
| P2 | Binding pattern in 4 classes | Maintenance burden | C2-R2 |
| P2 | Monolithic `AppConfig` (35+ fields) | Config sprawl | C2-R5 |
| P3 | `i18n.setup_i18n()` never called by `create_app()` | Dead code or unfinished feature | C2-R1 |
| P3 | Language double-source (framework + project `.ini` overlap) | Sync risk on framework upgrades | C2-R5 |

## 8. Confirmed Facts vs Inferences

### Confirmed (verified by reading code at `2fc6e6b`)
- 13 direct Sanic imports across 9 files (listed in §3.1).
- 30 function-level lazy imports across 15 files (listed in §4.2).
- No static circular dependency between `exception` and `system` (§4.3).
- Potential lazy cycle: `system.auth.middleware → exception` (items 26-30).
- `_deep_freeze` / `_freeze_value` defined in 4 locations (§4.4).
- 4 Binding pattern classes (§4.5).
- `i18n.setup_i18n()` is never called by `create_app()`.
- `middleware/cache.py` `Cache` class has zero instantiation sites in repo.
- `RoutePolicyDefinition` has no `signing_required` field.
- `system.auth` never imports `system.auth.tenant` at any level.
- Language `.ini` files exist in both `src/lingshu/language/` and `app/language/`.
- `app/resources/` does not exist.

### Inferences (not verified by runtime)
- `middleware/auth.py` is likely not wired into the active request pipeline
  (based on import analysis showing it's re-exported but not installed as
  middleware by `create_app()`).
- External projects may use `middleware/cache.Cache` — cannot be determined
  from repo-internal search alone.
- `extensions/i18n.py` may have been intended for lifecycle-based setup but
  was never connected.
