# Current Phase

Project: LingShu Framework
Current phase: C2.2A - tenant context and resolution foundation
Current branch: codex/phase-c2-tenant-context
Current issue: #17
Status: implementation complete, awaiting review
Next phase allowed: no

## Accepted Baseline

- Phase A accepted and merged.
- Phase B accepted and merged through PR #8.
- Phase C0 accepted and merged through PR #11.
- Phase C1 accepted and merged through PR #13.
- Phase C2.1 accepted and merged through PR #16 (merge commit: 398d042).

## Phase C2.2A Goal

Build tenant context, resolution protocol, fail-closed middleware, and
request-level binding on top of the C2.1 authentication foundation.

## Security Contracts

- **create_app() installs tenant middleware unconditionally.**
  Tenant-required routes with no resolver chain → 403/990124.
- **configure_tenant_resolution(app, chain) only sets/replaces the chain.**
  Middleware installation is idempotent.
- **lingshu.tenant is the sole public tenant module.**
- **Tenant resolution executes AFTER authentication.**
  No Principal → auth middleware returns 401 first.
- **Deny by default.** Unregistered/empty chain → 403.
- **claim is not trust.** ClaimTenantResolver requires explicit validator.
- **TenantContext is immutable** with deep-frozen attributes.
- **No str() conversion** of tenant identifiers.
- **CancelledError is never swallowed.** Tenant binding cleaned up on cancel.

## Test Results

- `tests/test_c2_tenant.py`: 111 passed, 0 failed.
- `tests/test_c2_auth.py`: 111 passed, 0 failed.
- Full suite: 430 passed, 0 failed (1 skipped: fresh-venv smoke).

## Scope Boundaries

### In scope (C2.2A)

- TenantContext immutable identity with frozen attributes.
- TenantResolutionResult enum (5 modes).
- TenantResolver Protocol and TenantResolverChain.
- ClaimTenantResolver (claim-based reference resolver).
- StubTenantResolver (test-only).
- Fail-closed tenant middleware (403).
- RoutePolicy tenant_required field with compile-time validation.
- ContextVar binding with cleanup (normal/exception/cancel).
- Error codes 990120-990124.
- lingshu.tenant public API + lingshu.request.tenant.

### Out of scope (prohibited)

```text
RBAC, role, permission, scope authorization
Gate, Policy, Resource Policy
Database query tenant_id auto-injection
Cross-tenant admin, impersonation
HMAC, nonce, replay protection
Rate limiting, concurrency store, idempotency store
OpenAPI, SDK, full DI
C2.2B, C3 or later phases
```

## Branch And Tracking

- Branch: `codex/phase-c2-tenant-context`
- Issue: `#17`
