# ADR-002: Public API And Deprecation Policy

## Status

Accepted (C2-RC, Issue #21)

## Context

The framework has multiple auth entry points with overlapping functionality:
a new Stable auth API (`lingshu.auth`), legacy `middleware/auth.py`, and
project-level re-exports (`app/__init__.py`). The PR #20 review identified
that the initial audit incorrectly classified `from lingshu.auth import Auth,
token_required` as Stable — this import path does not exist.

Without a formal API tier system and deprecation policy, there is no
governance for when import paths can be moved, renamed, or deleted.

## Decision

1. All public import paths are classified into tiers: Stable, Experimental,
   Internal, Legacy, Deprecated.
2. No import path is deleted until it is classified.
3. Stable API requires: compat shim + DeprecationWarning + migration docs +
   minimum 2 minor versions before deletion.
4. Legacy entry points cannot be deleted based solely on "zero internal
   consumers" — they get a compat shim and follow the deprecation cycle.
5. `lingshu.auth` exports only the new auth API (Principal, Authenticator,
   AuthenticatorChain, etc.). `Auth` and `token_required` are NOT in
   `lingshu.auth` — they are legacy symbols in `middleware/auth.py`.
6. `data_state`, `created_time`, `updated_time`, logical-delete fields are
   backend conventions. They do NOT enter the generic data core.
7. **Plan A (conservative classification).** Within the new auth and tenant
   facades, symbols are split into two tiers:

   - **Stable**: protocols (`Authenticator`, `TenantResolver`), facades and
     accessors (`configure_authentication`, `get_principal`, `require_principal`,
     `configure_tenant_resolution`, `get_tenant`, `require_tenant`), outcome
     and result types (`AuthResult`, `AuthenticationOutcome`,
     `AuthenticationRejected`, `TenantContext`, `TenantResolutionResult`,
     `TenantResolutionOutcome`), and value types (`Principal`).
   - **Experimental**: chain and concrete-implementation symbols
     (`AuthenticatorChain`, `JwtBearerAuthenticator`, `TenantResolverChain`,
     `ClaimTenantResolver`).

   Every symbol in a module's `__all__` must appear in exactly one tier
   (Stable or Experimental). This split is enforced by
   `tests/architecture/test_public_api_contract.py`.

## Consequences

- Developers can rely on Stable API not changing without warning.
- Legacy code gets a controlled sunset, not an abrupt removal.
- Scaffold templates must generate code using only Stable import paths.
- The classification table lives in `docs/architecture/public-api-contract.md`
  and `docs/architecture/architecture-contract.json`.

## Rejected Alternatives

- **Plan B (all new auth/tenant symbols Stable):** Classifying
  `AuthenticatorChain`, `JwtBearerAuthenticator`, `TenantResolverChain`, and
  `ClaimTenantResolver` as Stable from the start. Rejected: these chain and
  concrete-implementation symbols are the most likely to evolve as
  integrations accumulate; granting them the full Stable guarantee would
  freeze them prematurely and force deprecation cycles for routine
  improvements.
- **Delete legacy code immediately:** Breaks downstream projects that import
  `middleware/auth.py`. Rejected.
- **No tier system:** Makes it impossible to reason about API stability.
  Rejected.
- **"After C3" deletion date:** Arbitrary phase boundary. Deletion must follow
  the deprecation cycle, not a fixed date. Rejected (corrected in PR #20 review).

## Change Conditions

- A new tier may be added (e.g., "EOL") if the deprecation cycle proves
  insufficient. Requires a new ADR.
- Individual symbols may be reclassified between tiers with Xiao Gu review
  and an ADR update.
