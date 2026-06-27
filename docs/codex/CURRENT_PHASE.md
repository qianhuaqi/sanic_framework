# Current Phase

Project: LingShu Framework
Current phase: C2.2A - tenant context and resolution foundation
Current branch: codex/phase-c2-tenant-context
Current issue: #17
Current PR: #18
Status: accepted, awaiting merge
Next phase allowed: no

## Accepted Baseline

- Phase A accepted and merged.
- Phase B accepted and merged through PR #8.
- Phase C0 accepted and merged through PR #11.
- Phase C1 accepted and merged through PR #13.
- Phase C2.1 accepted and merged through PR #16 (merge commit: `398d042`).

## Phase C2.2A Goal

Build tenant context, resolution protocol, fail-closed middleware, and
request-level binding on top of the C2.1 authentication foundation.

## Security Contracts

- **create_app() installs tenant middleware unconditionally.**
  Tenant-required routes with no resolver chain → 403/990124.
- **configure_tenant_resolution(app, chain) only sets/replaces the chain.**
  Middleware installation is idempotent.
- **lingshu.tenant is the sole public tenant module.**
- **Tenant resolution executes after authentication.**
  No Principal → authentication middleware returns 401 first.
- **Deny by default.** Unregistered/empty resolver chain → 403.
- **Claim is not trust.** ClaimTenantResolver requires an explicit validator.
- **Only exact True succeeds.** False → FORBIDDEN; invalid validator results → INTERNAL_ERROR.
- **Tenant identifiers are strict strings.** No implicit conversion, empty values, or surrounding whitespace.
- **TenantContext is immutable** with deep-frozen attributes.
- **Control-flow exceptions are not swallowed.** Cancellation and process-control exceptions propagate.
- **Bindings are isolated and cleaned** on normal, exception, cancellation, and timeout paths.

## Test Results

- `tests/test_c2_tenant.py`: 127 passed, 0 failed.
- `tests/test_c2_auth.py`: 111 passed, 0 failed.
- Full suite: 446 passed, 0 failed, 1 skipped (optional fresh-venv smoke).
- `pip check`: no broken requirements.
- `git diff --check`: passed.

## Scope Boundaries

### In scope (C2.2A)

- TenantContext immutable identity with frozen attributes.
- TenantResolutionResult enum and safe outcome carrier.
- TenantResolver protocol and ordered TenantResolverChain.
- ClaimTenantResolver with sync/async validator support.
- StubTenantResolver for tests only.
- Fail-closed tenant middleware and stable 403 error mapping.
- RoutePolicy `tenant_required` field with compile-time validation.
- ContextVar binding with normal/exception/cancel/timeout cleanup.
- Error codes 990120-990124.
- `lingshu.tenant` public API and `lingshu.request.tenant`.

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
- PR: `#18`
- Accepted implementation commit: `5418f0b7b0cbe85223fa87aac3d46fae0594e7fd`
