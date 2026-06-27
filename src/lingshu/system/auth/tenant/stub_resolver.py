from __future__ import annotations

from typing import Any

from lingshu.system.auth.principal import Principal
from lingshu.system.auth.tenant.context import TenantContext
from lingshu.system.auth.tenant.result import TenantResolutionOutcome, TenantResolutionResult


class StubTenantResolver:
    """Deterministic tenant resolver for test suites.

    NOT for production use.  Allows tests to simulate any
    TenantResolutionResult without depending on JWT claims or external
    services.
    """

    resolver_id = "stub-tenant"

    def __init__(
        self,
        resolver_id: str = "stub-tenant",
        *,
        mode: str = "success",
        tenant_id: str = "test-tenant",
        attributes: dict[str, Any] | None = None,
        raise_exc: BaseException | None = None,
    ):
        self.resolver_id = resolver_id
        self._mode = mode
        self._tenant_id = tenant_id
        self._attributes = attributes
        self._raise_exc = raise_exc
        self.call_count = 0

    async def resolve(self, request, principal: Principal) -> TenantResolutionOutcome:
        self.call_count += 1

        if self._raise_exc is not None:
            raise self._raise_exc

        mode = self._mode

        if callable(mode):
            return mode(request, principal)

        if mode == TenantResolutionResult.SUCCESS or mode == "success":
            ctx = TenantContext.create(
                tenant_id=self._tenant_id,
                resolver_id=self.resolver_id,
                attributes=self._attributes,
            )
            return TenantResolutionOutcome.success(ctx)

        if mode == TenantResolutionResult.MISSING or mode == "missing":
            return TenantResolutionOutcome.missing(self.resolver_id)

        if mode == TenantResolutionResult.MALFORMED or mode == "malformed":
            return TenantResolutionOutcome.malformed(self.resolver_id, "Stub: malformed tenant")

        if mode == TenantResolutionResult.FORBIDDEN or mode == "forbidden":
            return TenantResolutionOutcome.forbidden(self.resolver_id, "Stub: forbidden tenant")

        if mode == TenantResolutionResult.INTERNAL_ERROR or mode == "internal_error":
            return TenantResolutionOutcome.internal_error(
                self.resolver_id,
                error=RuntimeError("Stub: simulated internal error"),
            )

        raise ValueError(f"Unknown StubTenantResolver mode: {mode!r}")
