# Dependency Rules

Status: Proposed — frozen by merge of the C2-RC PR
Source: `docs/architecture/src-target-boundaries.md` §4

## 1. Current Dependency State (Pre-Refactor)

The current codebase has not yet been split into target layers. Key facts:

- 13 direct Sanic imports across 9 files (see `src-convergence-audit.md` §3).
- 30 function-level lazy imports across 15 files (see `src-convergence-audit.md` §4.2).
- No static circular dependency between `exception` and `system`.
- Potential lazy cycle: `system.auth.middleware → exception` (lazy imports).
- `system.sanic_adapter` hardcodes auth/tenant binding attribute names
  (conceptual coupling, not import cycle).

## 2. Target Layer Dependency Rules

These rules apply to the target directory structure defined in
`src-target-boundaries.md` §3. They are enforced by machine boundary tests
once the target directories exist.

| Layer | May import | Must NOT import |
|---|---|---|
| `core/` | Standard library only | Sanic, JWT, DB drivers, any lingshu package |
| `security/auth/` | `core/`, PyJWT (`jwt_bearer.py` only) | Sanic, `adapters/`, `contrib/tenant/`, `data/`, `compat/` |
| `contrib/tenant/` | `core/`, `security/auth/` | Sanic, `adapters/`, `data/`, `compat/` |
| `data/` | `core/`, third-party drivers | Sanic, request proxy, `security/`, `contrib/`, `compat/` |
| `adapters/sanic/` | `core/`, `security/auth/` (types), `contrib/tenant/` (types), `response.py`, Sanic | `data/`, `compat/`, legacy `middleware/` |
| `compat/` | Legacy implementations | Must not be imported by `core/`, `security/`, `contrib/`, `data/`, `adapters/`, `app.py` |
| Top-level facades | `security/auth/`, `contrib/tenant/`, `adapters/sanic/`, `core/` | `compat/` directly, `data/` |

## 3. Auth And Adapter Separation

- `security/auth/` defines pure domain types (Principal, result, Protocol, Chain).
  Zero Sanic dependency.
- `adapters/sanic/auth_middleware.py` is Sanic middleware that depends on
  `security/auth/` to install middleware and build 401 responses.
- Direction: adapter → auth (one-way). Auth does NOT depend on adapter.

## 4. Tenant Positioning

- Tenant is an optional capability, not part of core authentication.
- `contrib/tenant/` depends on `security/auth/` (needs Principal).
- `security/auth/` never imports `contrib/tenant/`.
- Auth works correctly without tenant installed.

## 5. Sanic Import Boundary

- `core/` must NOT import Sanic — hard constraint.
- `adapters/sanic/` MAY import Sanic directly — expected and correct.
- Legacy `middleware/`, `app.py`, `response.py` currently import Sanic directly.
  These migrate into `adapters/sanic/` during refactoring phases (R1–R6).
