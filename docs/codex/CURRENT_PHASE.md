# Current Phase

Project: LingShu Framework
Current phase: C2.1 - authentication foundation
Current branch: codex/phase-c2-authentication
Current issue: #15
Status: implementation in progress
Next phase allowed: no

## Accepted Baseline

- Phase A accepted and merged.
- Phase B accepted and merged through PR #8.
- Phase C0 research convergence accepted and merged through PR #11.
- Phase C1 request execution foundation accepted and merged through PR #13.
- C1 merge commit: `0bbd1b1`.
- Phase C1 tests previously recorded: 203 passed, 0 new regressions.

## Phase C2.1 Goal

Build the authentication foundation required by all later security work:

```text
Principal (immutable identity)
AuthResult taxonomy (missing/malformed/invalid/expired/revoked/internal_error)
Authenticator Protocol + AuthenticatorChain (ordered registry + executor)
JwtBearerAuthenticator (Bearer/JWT reference implementation)
StubAuthenticator (deterministic test authenticator)
Authentication middleware gate (public/protected, 401 + WWW-Authenticate)
Principal binding to RequestExecutionContext (ContextVar isolation + cleanup)
```

## Scope Boundaries

### In scope (C2.1)

- Principal immutable identity with frozen scopes and read-only claims.
- AuthResult enum with distinct failure modes and RFC 6750 WWW-Authenticate mapping.
- AuthenticationOutcome carrier (result + principal + safe description).
- Authenticator Protocol and AuthenticatorChain with ordered registration,
  first-success short-circuit, missing fall-through, invalid short-circuit.
- JwtBearerAuthenticator: strict Bearer parsing, alg=none rejection, configurable
  issuer/audience/leeway, exception wrapping, no internal detail leakage.
- StubAuthenticator for deterministic test scenarios.
- Authentication middleware: public route exemption, protected route enforcement,
  stable 401 with WWW-Authenticate, no token/secret/exception leakage.
- Principal ContextVar binding with guaranteed reset on normal return,
  exception, cancellation, and after-task cleanup.
- Multi-app isolation: each app has its own AuthenticatorChain.
- Error codes 990110-990116 for authentication failure modes.

### Out of scope (prohibited in C2.1)

```text
Tenant resolution, RBAC, permissions, 403
HMAC signing, nonce, replay protection
Rate limiting, concurrency store, idempotency store
JWT refresh token flow
Session authentication
API Key authentication
OpenAPI / TypeScript SDK
Full DI container or Extension Manifest runtime
Outbox, Audit implementation or OTel exporter
lingshu-ms, Go runtime, Vue runtime or device gateway
```

## Implemented Components

### Principal (`src/lingshu/system/auth/principal.py`)

- Frozen dataclass: `subject`, `authenticator_id`, `scopes` (frozenset), `claims` (MappingProxyType).
- `create()` factory normalises input types.
- `has_scope()` for future authorization use.
- `__repr__` omits claims and scopes to prevent log leakage.

### AuthResult (`src/lingshu/system/auth/result.py`)

- `SUCCESS`, `MISSING`, `MALFORMED`, `INVALID`, `EXPIRED`, `REVOKED`, `INTERNAL_ERROR`.
- `www_authenticate_error` maps to RFC 6750 error codes.
- `AuthenticationOutcome` dataclass with factory methods per result.
- `safe_description` never leaks `internal_error` details.

### Authenticator / AuthenticatorChain (`src/lingshu/system/auth/authenticator.py`)

- `Authenticator` is a `@runtime_checkable Protocol` with `authenticator_id` and `async authenticate()`.
- `AuthenticatorChain` executes authenticators in registration order.
- First SUCCESS short-circuits.
- MISSING does NOT short-circuit (later authenticator may succeed).
- INVALID/MALFORMED/EXPIRED/REVOKED/INTERNAL_ERROR immediately short-circuit.
- All-MISSING returns MISSING.
- Unexpected exceptions wrapped to INTERNAL_ERROR.

### JwtBearerAuthenticator (`src/lingshu/system/auth/jwt_bearer.py`)

- `authenticator_id = "jwt-bearer"`.
- Strict `Authorization: Bearer <token>` parsing.
- Algorithm allowlist (HS/RS/ES/PS/EdDSA); `alg=none` rejected unconditionally.
- Configurable `issuer`, `audience`, `leeway`, `require_exp`.
- Distinguishes EXPIRED, INVALID (signature), MALFORMED (decode/structure).
- `encode_token()` / `encode_expired_token()` utilities for test token generation.
- Never leaks exception text into `error_description`.

### StubAuthenticator (`src/lingshu/system/auth/stub_authenticator.py`)

- Deterministic authenticator for test suites.
- Supports all AuthResult modes via `mode` parameter (string or enum).
- Callable mode for request-dependent outcomes.
- `for_result()` classmethod convenience.

### Middleware (`src/lingshu/system/auth/middleware.py`)

- `install_authentication_middleware(app)` installs the request gate.
- Reads `route_policy.public` and `route_policy.auth_required` from execution context.
- Public or `auth_required=False` routes are exempt.
- No chain registered: middleware is transparent.
- Chain registered but empty: 401 with error code 990116 (scheme not registered).
- On failure: stable 401 JSON response with WWW-Authenticate header.
- On success: binds Principal to ContextVar.
- 401 responses include `request_id` / `trace_id` from execution context.
- 401 responses never leak tokens, secrets, exception text, or internal class names.
- `_build_www_authenticate()` produces RFC 6750 compliant header.
- `set_authenticator_chain(app, chain)` / `get_authenticator_chain(app)` for app-level config.

### Context Binding (`src/lingshu/system/auth/context.py`)

- `current_principal` ContextVar for concurrent isolation.
- `_PrincipalBinding` with `__enter__` / `__exit__` / `reset()` / `detach_after_task()`.
- `bind_principal()` creates binding; middleware calls `__enter__()`.
- `require_principal()` raises `NoRequestContextError` if unbound.
- `principal_scope()` context manager for test/manual use.

### Cleanup Integration (`src/lingshu/system/sanic_adapter.py`)

- `reset_request_context()` calls `_reset_principal_binding()`.
- `detach_request_context_after_task()` calls `principal_binding.detach_after_task()`.
- Both paths are defensive (try/except) and idempotent.

### Proxies (`src/lingshu/system/proxies.py`)

- `RequestProxy.principal` property returns `current_principal.get()`.

### Error Codes

- 990110: Authentication credential is missing
- 990111: Authentication credential is malformed
- 990112: Authentication credential is invalid
- 990113: Authentication credential has expired
- 990114: Authentication credential has been revoked
- 990115: Authentication service error
- 990116: Authentication scheme is not registered

## Test Coverage

`tests/test_c2_auth.py` — 74 tests covering:

- Principal immutability, frozen claims, validation, repr leakage.
- AuthResult taxonomy, www_authenticate_error mapping.
- AuthenticationOutcome factories, safe_description.
- AuthenticatorChain: first-success short-circuit, missing fall-through,
  invalid short-circuit, all-missing, empty chain, exception wrapping,
  registration validation, ordering, lookup, is_empty.
- StubAuthenticator: all 7 modes, callable mode, for_result.
- JwtBearerAuthenticator: success, missing, malformed scheme, malformed JWT,
  invalid signature, expired, alg=none prohibition, empty secret/algorithm,
  issuer verification, audience verification, scopes as string.
- Principal binding: require without binding, bind+get+reset, concurrent
  isolation (100 and 500 tasks), reset on exception.
- Protocol conformance: StubAuthenticator and JwtBearerAuthenticator satisfy
  the Authenticator Protocol.
- Error code stability: all 6 failure codes match expected values.
- AuthenticationRejected bridge exception.
- Public route exemption even with empty chain.
- Protected route 401 with WWW-Authenticate for missing/invalid/expired.
- Protected route success binds principal to response.
- No chain registered: middleware transparent.
- Empty chain: 401 scheme-not-registered.
- 401 does not leak internal exception details.
- Multi-app isolation: independent chains produce different results.
- Concurrent request isolation: 20 concurrent requests with distinct principals.

## Current Prohibitions

Do not implement or refactor the following in C2.1:

```text
JWT/API Key/Session authentication (beyond Bearer/JWT reference)
resource authorization and real TenantContext resolution
HMAC signing, nonce and replay protection
rate limiting, concurrency store or idempotency store
MySQL/SQLite/MongoDB/Redis backend redesign
Pydantic Schema facade
OpenAPI 3.1 compiler or TypeScript SDK
full DI container or Extension Manifest runtime
Outbox, Audit implementation or OTel exporter
lingshu-ms, Go runtime, Vue runtime or device gateway
```

Also prohibited:

- no business imports from `lingshu.system` (business code must not import `lingshu.system`);
- no unowned `asyncio.create_task()`;
- no swallowing `CancelledError`;
- no secrets, private paths, credentials or network addresses;
- no starting C2.2 before independent C2.1 acceptance.

## Branch And Tracking

- Branch: `codex/phase-c2-authentication`
- Issue: `#15`
