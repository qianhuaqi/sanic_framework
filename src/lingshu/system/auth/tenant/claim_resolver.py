from __future__ import annotations

from typing import Any, Callable

from lingshu.system.auth.principal import Principal
from lingshu.system.auth.tenant.context import TenantContext
from lingshu.system.auth.tenant.result import TenantResolutionOutcome


class ClaimTenantResolver:
    """Reference claim-based tenant resolver.

    Reads a configured claim from the authenticated Principal and validates
    it through an explicit validator/membership checker.

    Security properties:
    - The claim name must be explicitly configured.
    - The claim value must originally be a non-empty string (no str() conversion).
    - A claim existing does NOT mean it is trusted — the validator must pass.
    - Validator rejection → FORBIDDEN.
    - Validator exception → INTERNAL_ERROR (never leaked).
    - No database, network, or external identity service dependency.
    """

    resolver_id = "claim-tenant"

    def __init__(
        self,
        *,
        claim_name: str,
        validator: Callable[[str, Principal], bool] | Callable[[str, Principal], None],
        resolver_id: str = "claim-tenant",
        attributes_claim: str | None = None,
    ):
        if not claim_name:
            raise ValueError("ClaimTenantResolver requires a non-empty claim_name")
        if validator is None:
            raise ValueError("ClaimTenantResolver requires an explicit validator")
        self._claim_name = claim_name
        self._validator = validator
        self.resolver_id = resolver_id
        self._attributes_claim = attributes_claim

    async def resolve(self, request, principal: Principal) -> TenantResolutionOutcome:
        if principal is None:
            return TenantResolutionOutcome.missing(self.resolver_id)

        raw_value = principal.claims.get(self._claim_name)

        if raw_value is None:
            return TenantResolutionOutcome.missing(self.resolver_id)

        if not isinstance(raw_value, str):
            return TenantResolutionOutcome.malformed(
                self.resolver_id,
                "Tenant claim is not a string",
            )

        if not raw_value.strip():
            return TenantResolutionOutcome.malformed(
                self.resolver_id,
                "Tenant claim is an empty string",
            )

        try:
            result = self._validator(raw_value, principal)
        except Exception as exc:
            return TenantResolutionOutcome.internal_error(
                self.resolver_id,
                error=exc,
            )

        if result is False:
            return TenantResolutionOutcome.forbidden(
                self.resolver_id,
                "Validator rejected tenant access",
            )

        attributes: dict[str, Any] = {}
        if self._attributes_claim:
            raw_attrs = principal.claims.get(self._attributes_claim)
            if isinstance(raw_attrs, dict):
                attributes = dict(raw_attrs)

        tenant_context = TenantContext.create(
            tenant_id=raw_value,
            resolver_id=self.resolver_id,
            attributes=attributes if attributes else None,
        )
        return TenantResolutionOutcome.success(tenant_context)
