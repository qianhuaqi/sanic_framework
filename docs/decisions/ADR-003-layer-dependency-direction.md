# ADR-003: Layer Dependency Direction

## Status

Accepted (C2-RC, Issue #21)

## Context

The current codebase has not been split into target layers. `system/` contains
most framework logic, with conceptual coupling and lazy import cycles. The
PR #20 audit confirmed:

- No static circular dependency between `exception` and `system`.
- Potential lazy cycle: `system.auth.middleware → exception` (lazy imports).
- `system.sanic_adapter` hardcodes auth/tenant binding attribute names.
- 13 direct Sanic imports across 9 files.
- 30 function-level lazy imports across 15 files.

The target architecture (defined in `src-target-boundaries.md`) introduces
`core/`, `security/auth/`, `contrib/tenant/`, `data/`, `adapters/sanic/`,
and `compat/` layers. Dependency direction rules must be established before
any refactoring begins.

## Decision

1. `core/` imports only the standard library. Zero external dependencies.
2. `security/auth/` is a pure domain layer. It imports `core/` and PyJWT only.
   It must NOT import Sanic, adapters, tenant, data, or compat.
3. `contrib/tenant/` is an optional capability. It imports `core/` and
   `security/auth/`. It must NOT import Sanic, adapters, data, or compat.
4. `data/` imports `core/` and third-party drivers. It must NOT import Sanic,
   request proxy, security, tenant, or compat.
5. `adapters/sanic/` imports `core/`, security types, tenant types, and Sanic.
   It must NOT import data, compat, or legacy middleware.
6. `compat/` holds legacy implementations. It must NOT be imported by any
   new layer (core, security, contrib, data, adapters).
7. Auth does NOT depend on adapter. Adapter depends on auth. One-way.

## Consequences

- Auth domain is portable — it can be reused with a non-Sanic adapter.
- `core/` is maximally stable — no external dependencies to track.
- Machine boundary tests enforce these rules programmatically.
- Future refactoring phases (R1–R6) must respect these constraints.

## Rejected Alternatives

- **Allow auth to depend on Sanic adapter:** Makes the entire auth package
  non-portable. Rejected.
- **Merge adapters into their domain packages:** Violates separation of
  concerns. Adapter code is framework-specific (Sanic); domain code is not.
  Rejected.

## Change Conditions

- If a second adapter is added (e.g., ASGI, FastAPI), the rules remain the
  same: each adapter depends on domain layers, not vice versa.
- If `core/` needs a shared utility that requires a third-party package, a
  new ADR must justify the exception.
