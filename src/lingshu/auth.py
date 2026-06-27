"""LingShu public authentication API.

This is the stable public entry point for authentication.  Business code
should import from ``lingshu.auth`` — never from ``lingshu.system``.

Public API:
    - Principal: immutable authenticated identity.
    - AuthResult: authentication outcome taxonomy.
    - AuthenticationOutcome: carrier for a result + optional principal.
    - Authenticator: protocol for credential verifiers.
    - AuthenticatorChain: ordered authenticator registry and executor.
    - JwtBearerAuthenticator: official Bearer/JWT reference implementation.
    - configure_authentication(app, chain): register an AuthenticatorChain.
    - get_principal(): get the current request's Principal or None.
    - require_principal(): get the current Principal or raise.

Usage::

    from lingshu.auth import (
        AuthenticatorChain,
        JwtBearerAuthenticator,
        configure_authentication,
    )

    chain = AuthenticatorChain()
    chain.register(JwtBearerAuthenticator(
        secret="your-secret",
        algorithms=["HS256"],
        issuer="your-issuer",
    ))
    configure_authentication(app, chain)
"""

from lingshu.system.auth.principal import Principal
from lingshu.system.auth.result import AuthResult, AuthenticationOutcome
from lingshu.system.auth.authenticator import (
    Authenticator,
    AuthenticatorChain,
    AuthenticationRejected,
)
from lingshu.system.auth.jwt_bearer import JwtBearerAuthenticator

__all__ = [
    "AuthResult",
    "AuthenticationOutcome",
    "AuthenticationRejected",
    "Authenticator",
    "AuthenticatorChain",
    "JwtBearerAuthenticator",
    "Principal",
    "configure_authentication",
    "get_principal",
    "require_principal",
]


def configure_authentication(raw_app, chain: AuthenticatorChain) -> AuthenticatorChain:
    """Register or replace the AuthenticatorChain on a Sanic app.

    This is the public entry point for enabling authentication on an app
    created via ``lingshu.create_app()`` or a scaffolded project.

    ``create_app()`` installs the authentication middleware unconditionally;
    this function only sets the chain.  Calling it more than once replaces
    the previous chain without installing additional middleware.
    """
    from lingshu.system.auth.middleware import set_authenticator_chain
    set_authenticator_chain(raw_app, chain)
    return chain


def get_principal():
    """Return the current request's Principal, or None.

    Returns None if there is no principal bound (e.g. public route).
    Raises NoRequestContextError if called outside a request context.
    """
    from lingshu.system.execution import current_execution_context
    current_execution_context()  # raises if no context
    from lingshu.system.auth.context import current_principal
    return current_principal.get()


def require_principal() -> Principal:
    """Return the current Principal or raise if none is bound.

    Raises NoRequestContextError if called outside a request context.
    """
    from lingshu.system.execution import current_execution_context
    current_execution_context()  # raises if no context
    from lingshu.system.auth.context import require_principal as _require
    return _require()
