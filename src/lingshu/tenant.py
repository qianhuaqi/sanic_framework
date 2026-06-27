"""LingShu public tenant resolution API.

This is the stable public entry point for tenant context.  Business code
should import from ``lingshu.tenant`` — never from ``lingshu.system``.

Public API:
    - TenantContext: immutable tenant identity.
    - TenantResolutionResult: resolution outcome taxonomy.
    - TenantResolutionOutcome: carrier for a result + optional context.
    - TenantResolver: protocol for tenant resolvers.
    - TenantResolverChain: ordered resolver registry and executor.
    - ClaimTenantResolver: official claim-based reference resolver.
    - configure_tenant_resolution(app, chain): register a TenantResolverChain.
    - get_tenant(): get the current request's TenantContext or None.
    - require_tenant(): get the current TenantContext or raise.
"""

from lingshu.system.auth.tenant.context import TenantContext
from lingshu.system.auth.tenant.result import TenantResolutionResult, TenantResolutionOutcome
from lingshu.system.auth.tenant.resolver import TenantResolver, TenantResolverChain
from lingshu.system.auth.tenant.claim_resolver import ClaimTenantResolver

__all__ = [
    "ClaimTenantResolver",
    "TenantContext",
    "TenantResolutionOutcome",
    "TenantResolutionResult",
    "TenantResolver",
    "TenantResolverChain",
    "configure_tenant_resolution",
    "get_tenant",
    "require_tenant",
]


def configure_tenant_resolution(raw_app, chain: TenantResolverChain) -> TenantResolverChain:
    """Register or replace the TenantResolverChain on a Sanic app.

    ``create_app()`` installs the tenant middleware unconditionally;
    this function only sets the chain.
    """
    from lingshu.system.auth.tenant.middleware import set_tenant_resolver_chain
    set_tenant_resolver_chain(raw_app, chain)
    return chain


def get_tenant():
    """Return the current request's TenantContext, or None.

    Returns None if there is no tenant bound (e.g. non-tenant-required route).
    Raises NoRequestContextError if called outside a request context.
    """
    from lingshu.system.execution import current_execution_context
    current_execution_context()  # raises if no context
    from lingshu.system.auth.tenant.binding import current_tenant
    return current_tenant.get()


def require_tenant() -> TenantContext:
    """Return the current TenantContext or raise if none is bound.

    Raises NoRequestContextError if called outside a request context.
    """
    from lingshu.system.execution import current_execution_context
    current_execution_context()  # raises if no context
    from lingshu.system.auth.tenant.binding import require_tenant as _require
    return _require()
