from __future__ import annotations

import contextvars
from contextlib import contextmanager

from lingshu.system.auth.principal import Principal
from lingshu.system.errors import NoRequestContextError


current_principal: contextvars.ContextVar[Principal | None] = contextvars.ContextVar(
    "lingshu_current_principal",
    default=None,
)


class _PrincipalBinding:
    def __init__(self, principal: Principal):
        self.principal = principal
        self.token: contextvars.Token | None = None
        self.reset_done = False

    def __enter__(self):
        if self.token is None:
            self.token = current_principal.set(self.principal)
        return self.principal

    def __exit__(self, exc_type, exc, tb):
        self.reset()

    def reset(self):
        if self.token is not None and not self.reset_done:
            current_principal.reset(self.token)
            self.reset_done = True
            self.token = None

    def detach_after_task(self):
        self.reset_done = True
        self.token = None
        self.principal = None  # type: ignore[assignment]


def bind_principal(principal: Principal) -> _PrincipalBinding:
    """Bind a Principal to the current execution context.

    Returns a binding object whose ``reset()`` must be called during cleanup.
    """
    return _PrincipalBinding(principal)


def current_principal_or_none() -> Principal | None:
    return current_principal.get()


def require_principal() -> Principal:
    """Return the current Principal or raise if none is bound."""
    principal = current_principal.get()
    if principal is None:
        raise NoRequestContextError("No authenticated principal is bound to the current request")
    return principal


# Public aliases matching the naming convention used elsewhere.
get_current_principal = current_principal_or_none


@contextmanager
def principal_scope(principal: Principal):
    binding = bind_principal(principal)
    try:
        with binding:
            yield principal
    finally:
        pass  # reset already handled by binding.__exit__
