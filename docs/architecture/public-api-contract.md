# Public API Contract

Status: Frozen (C2-RC, based on PR #20 architecture audit)
Source: `docs/architecture/src-migration-roadmap.md` (API Stability Tiers)

## 1. API Tiers

| Tier | Definition | Move/Rename | Deletion |
|---|---|---|---|
| **Stable** | Documented public API | Compat shim + DeprecationWarning + migration docs + 2 minor versions | After deprecation cycle + scaffold update |
| **Experimental** | Public but not yet stable | Compat shim recommended, PendingDeprecationWarning | 1 minor version + migration docs |
| **Internal** | `system.*` not documented as public | Free to move | If internal audit confirms zero consumers |
| **Legacy** | Old importable entry points still in use | Move to `compat/` with DeprecationWarning | Per deprecation cycle |
| **Deprecated** | Already in `compat/` or marked deprecated | N/A | Next major version |

## 2. Classification: Authentication API

Authentication is split across four entry points:

| Import path | Tier | Notes |
|---|---|---|
| `from lingshu.auth import Principal, Authenticator, AuthenticatorChain, JwtBearerAuthenticator, AuthenticationOutcome, AuthenticationRejected, AuthResult, configure_authentication, get_principal, require_principal` | **Stable** | New auth API (C2.1/C2.2A). Documented, tested. |
| `from lingshu.auth import Auth, token_required` | **Does NOT exist** | `lingshu.auth` does not export these. |
| `from lingshu.middleware.auth import Auth, token_required` | **Legacy** | Legacy JWT auth class. Gets compat shim in R1. |
| `from lingshu.extensions.auth import Auth, token_required` | **Legacy facade** | Thin re-export of `middleware.auth`. |
| `from app import Auth` | **Project compat entry** | Project-generated re-export. Updated in R6 scaffold. |

## 3. Classification: Tenant API

| Import path | Tier | Notes |
|---|---|---|
| `from lingshu.tenant import TenantContext, TenantResolutionResult, TenantResolutionOutcome, TenantResolver, TenantResolverChain, ClaimTenantResolver, configure_tenant_resolution, get_tenant, require_tenant` | **Stable** | New tenant API (C2.2A). Documented, tested. |
| `from lingshu.system.auth.tenant.*` | **Internal** | Will move to `contrib/tenant/` in R3. |

## 4. Classification: Top-Level Facade

| Import path | Tier | Notes |
|---|---|---|
| `from lingshu import APIException, abort, app, config, db, language, logger, request` | **Stable** | Top-level facade re-exports. |

## 5. Classification: Other Stable APIs

| Import path | Tier | Notes |
|---|---|---|
| `from lingshu.router import RoutePolicy` | **Stable** | Public route policy. |
| `from lingshu.model import Model, BaseModel` | **Stable** | Data model base. |
| `from lingshu.model import BusinessModel` | **Stable** (will move to scaffold) | Project service-layer pattern. Decoupled in R6, eventually scaffold-owned. |

## 6. Classification: Legacy/Internal

| Import path | Tier | Notes |
|---|---|---|
| `from lingshu.middleware.auth import Auth` | Legacy → Deprecated | Compat shim in R1. |
| `from lingshu.middleware.cache import Cache` | Internal | Zero consumers. Classified before deletion. |
| `from lingshu.system.auth.principal import Principal` | Internal | Used by facade, not documented as public. |
| `from lingshu.system.sanic_adapter import *` | Internal | Compat re-export after R2 split. |

## 7. Rules

1. No import path is deleted until it is classified into a tier.
2. Stable API deletion requires a version/deprecation cycle.
3. Legacy entry points cannot be deleted based solely on "zero internal consumers."
4. `data_state`, `created_time`, `updated_time`, logical-delete fields are
   backend conventions — they do NOT enter the generic data core.
5. No `public/` directory is created. Top-level facades remain in place.
