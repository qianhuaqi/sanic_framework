# ADR-004: Tenant As Optional Capability

## Status

Accepted (C2-RC, Issue #21)

## Context

Tenant resolution was originally placed under `system/auth/tenant/` — inside
the auth module. This creates the impression that tenant is a required part
of authentication. In practice, many deployments do not use multi-tenancy.

The PR #20 review decided to move tenant to `contrib/tenant/` as an optional
capability. This decision must be frozen so that future refactoring phases
do not re-debate it.

## Decision

1. Tenant is an optional capability, not part of core authentication.
2. Auth must work correctly without tenant installed.
3. `contrib/tenant/` depends on `security/auth/` (needs Principal), but
   `security/auth/` never imports `contrib/tenant/`.
4. In the target architecture, tenant middleware lives in
   `adapters/sanic/tenant_middleware.py` (Sanic-specific). Tenant domain
   types (TenantContext, TenantResolver, etc.) live in `contrib/tenant/`.
5. The Stable public API for tenant (`lingshu.tenant`) remains unchanged.

## Consequences

- Projects that do not need multi-tenancy can skip tenant installation entirely.
- Auth module stays smaller and focused on identity verification.
- Machine boundary tests verify `contrib/tenant/` does not import Sanic or
  adapters.

## Rejected Alternatives

- **Keep tenant inside auth:** Couples auth to tenant. Auth module becomes
  larger than necessary. Rejected.
- **Make tenant a required capability:** Forces all projects to configure
  tenant even if they don't use it. Rejected.

## Change Conditions

- If tenant becomes a mandatory part of the framework's identity model, this
  ADR must be superseded by a new one.
