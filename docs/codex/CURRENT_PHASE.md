# Current Phase

Project: LingShu Framework
Current phase: C2.1 - authentication foundation
Current branch: codex/phase-c2-authentication
Current issue: #15
Current PR: #16
Status: accepted, awaiting merge
Next phase allowed: no

## Accepted Baseline

- Phase A accepted and merged.
- Phase B accepted and merged through PR #8.
- Phase C0 research convergence accepted and merged through PR #11.
- Phase C1 request execution foundation accepted and merged through PR #13.
- C1 merge commit: `0bbd1b1`.

## Phase C2.1 Goal

Build the authentication foundation: Principal, AuthResult, AuthenticatorChain,
JwtBearerAuthenticator, fail-closed middleware, ContextVar binding.

## Security Contracts

- **create_app() installs authentication middleware unconditionally.**
  Protected routes with no chain registered → 401/990116.
- **configure_authentication(app, chain) only sets/replaces the chain.**
  It does not install middleware. Calling it twice replaces the chain.
- **Middleware installation is idempotent.**
  Repeated calls to install_authentication_middleware are no-ops.
- **lingshu.auth is the sole public authentication module.**
  No AuthFacade; `lingshu.auth` always resolves to the module.
- **Scaffold controller template defaults to auth_required=True.**
  Generated CRUD endpoints are protected by default.
- **JwtBearerAuthenticator has no token signing methods.**
  Token generation uses test-only helpers (jwt_test_helpers.py).
- **JWT scopes: each list/tuple/set item must be a non-empty string.**
  Numbers, None, empty strings → MALFORMED (no str() conversion).
- **AuthenticationRejected uses framework-fixed descriptions.**
  Authenticator error_description never reaches str(exception).
- **CancelledError is never swallowed.**
  Principal binding is cleaned up on cancellation before the next request can observe context.

## Test Results

- `tests/test_c2_auth.py`: 111 passed, 0 failed.
- Full suite: 319 passed, 0 failed, 1 skipped (fresh-venv smoke).
- `pip check`: no broken requirements.
- `git diff --check`: passed.

## Scope Boundaries

### In scope (C2.1)

- Principal immutable identity with frozen scopes and claims.
- AuthResult enum with RFC 6750 WWW-Authenticate mapping.
- AuthenticatorChain with ordered registration and short-circuit semantics.
- JwtBearerAuthenticator (Bearer/JWT reference implementation).
- Fail-closed authentication middleware.
- Principal ContextVar binding with cleanup (normal/exception/cancel).
- Error codes 990110-990116.

### Out of scope (prohibited)

```text
Tenant resolution, RBAC, permissions, 403
HMAC signing, nonce, replay protection
Rate limiting, concurrency store, idempotency store
JWT refresh token flow, Session auth, API Key auth
OpenAPI / TypeScript SDK
Full DI, Extension Manifest runtime, Outbox, Audit, OTel
lingshu-ms, Go runtime, Vue runtime, device gateway
```

## Branch And Tracking

- Branch: `codex/phase-c2-authentication`
- Issue: `#15`
- PR: `#16`
