from __future__ import annotations

import contextvars
from contextlib import contextmanager

from lingshu.system.auth.tenant.context import TenantContext
from lingshu.system.errors import NoRequestContextError


current_tenant: contextvars.ContextVar[TenantContext | None] = contextvars.ContextVar(
    "lingshu_current_tenant",
    default=None,
)


class _TenantBinding:
    def __init__(self, tenant_context: TenantContext):
        self.tenant_context = tenant_context
        self.token: contextvars.Token | None = None
        self.reset_done = False

    def __enter__(self):
        if self.token is None:
            self.token = current_tenant.set(self.tenant_context)
        return self.tenant_context

    def __exit__(self, exc_type, exc, tb):
        self.reset()

    def reset(self):
        if self.token is not None and not self.reset_done:
            current_tenant.reset(self.token)
            self.reset_done = True
            self.token = None

    def detach_after_task(self):
        self.reset_done = True
        self.token = None
        self.tenant_context = None  # type: ignore[assignment]


def bind_tenant(tenant_context: TenantContext) -> _TenantBinding:
    """Bind a TenantContext to the current execution context."""
    return _TenantBinding(tenant_context)


def current_tenant_or_none() -> TenantContext | None:
    return current_tenant.get()


def require_tenant() -> TenantContext:
    """Return the current TenantContext or raise if none is bound."""
    tenant = current_tenant.get()
    if tenant is None:
        raise NoRequestContextError("No tenant context is bound to the current request")
    return tenant


@contextmanager
def tenant_scope(tenant_context: TenantContext):
    binding = bind_tenant(tenant_context)
    try:
        with binding:
            yield tenant_context
    finally:
        pass
