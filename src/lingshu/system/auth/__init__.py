"""LingShu authentication foundation (Phase C2.1).

Public API:
    - Principal: immutable authenticated identity.
    - AuthResult: authentication outcome taxonomy.
    - AuthenticationOutcome: carrier for a result + optional principal.
    - Authenticator: protocol for credential verifiers.
    - AuthenticatorChain: ordered authenticator registry and executor.
    - JwtBearerAuthenticator: official Bearer/JWT reference implementation.
    - StubAuthenticator: deterministic authenticator for tests.
    - current_principal / require_principal: request-scoped access.

Design constraints (Phase C2.1 scope):
    - No tenant resolution, RBAC, permissions, or scope authorization.
    - No HMAC, nonce, replay protection, rate limiting, or idempotency.
    - Internal exceptions must never leak to the client.
    - missing and invalid are strictly distinguished.
    - alg=none and hand-rolled crypto are prohibited.
"""

from lingshu.system.auth.principal import Principal
from lingshu.system.auth.result import AuthResult, AuthenticationOutcome
from lingshu.system.auth.authenticator import (
    Authenticator,
    AuthenticatorChain,
    AuthenticationRejected,
)
from lingshu.system.auth.context import (
    current_principal,
    require_principal,
    bind_principal,
)
from lingshu.system.auth.jwt_bearer import JwtBearerAuthenticator
from lingshu.system.auth.stub_authenticator import StubAuthenticator

__all__ = [
    "AuthResult",
    "AuthenticationOutcome",
    "AuthenticationRejected",
    "Authenticator",
    "AuthenticatorChain",
    "JwtBearerAuthenticator",
    "Principal",
    "StubAuthenticator",
    "bind_principal",
    "current_principal",
    "require_principal",
]
