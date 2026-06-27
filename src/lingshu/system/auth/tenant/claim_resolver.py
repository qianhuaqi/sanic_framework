from __future__ import annotations

import asyncio
import inspect
from typing import Any, Awaitable, Callable, Union

from lingshu.system.auth.principal import Principal
from lingshu.system.auth.tenant.context import TenantContext
from lingshu.system.auth.tenant.result import TenantResolutionOutcome


# A validator may be sync (returns bool) or async (returns Awaitable[bool]).
# Only ``True`` (identity-checked) means success.  ``False`` means FORBIDDEN.
# Any other return value (None, int, str, object, ...) is INTERNAL_ERROR.
ValidatorResult = Union[bool, Awaitable[bool]]
Validator = Callable[[str, Principal], ValidatorResult]


class ClaimTenantResolver:
    """Reference claim-based tenant resolver.

    Reads a configured claim from the authenticated Principal and validates
    it through an explicit validator/membership checker.

    Security properties:
    - The claim name must be explicitly configured.
    - The claim value must originally be a non-empty string (no str() conversion).
    - A claim existing does NOT mean it is trusted — the validator must pass.
    - **Fail-closed:** only a return value *exactly* ``True`` means success.
      ``False`` → FORBIDDEN.  Any other return (None, int, str, object) or
      an exception → INTERNAL_ERROR.
    - Claim present but value ``None`` → MALFORMED (short-circuit, not MISSING).
    - ``asyncio.CancelledError`` is always re-raised (never swallowed).
    - No database, network, or external identity service dependency.
    """

    resolver_id = "claim-tenant"

    def __init__(
        self,
        *,
        claim_name: str,
        validator: Validator,
        resolver_id: str = "claim-tenant",
    ):
        if not isinstance(claim_name, str) or not claim_name:
            raise ValueError("ClaimTenantResolver requires a non-empty claim_name")
        if validator is None:
            raise ValueError("ClaimTenantResolver requires an explicit validator")
        if not isinstance(resolver_id, str) or not resolver_id:
            raise ValueError("ClaimTenantResolver requires a non-empty resolver_id")
        if resolver_id != resolver_id.strip():
            raise ValueError(
                "ClaimTenantResolver resolver_id must not have leading or trailing whitespace"
            )
        self._claim_name = claim_name
        self._validator = validator
        self.resolver_id = resolver_id

    async def resolve(self, request, principal: Principal) -> TenantResolutionOutcome:
        if principal is None:
            return TenantResolutionOutcome.missing(self.resolver_id)

        if self._claim_name not in principal.claims:
            return TenantResolutionOutcome.missing(self.resolver_id)

        raw_value = principal.claims[self._claim_name]

        if raw_value is None:
            return TenantResolutionOutcome.malformed(
                self.resolver_id,
                "Tenant claim value is None",
            )

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
            if inspect.isawaitable(result):
                result = await result
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except BaseException as exc:  # noqa: BLE001 — fail-closed: never leak
            return TenantResolutionOutcome.internal_error(
                self.resolver_id,
                error=exc,
            )

        # Fail-closed: only the exact boolean True is success.
        if result is True:
            tenant_context = TenantContext.create(
                tenant_id=raw_value,
                resolver_id=self.resolver_id,
            )
            return TenantResolutionOutcome.success(tenant_context)

        if result is False:
            return TenantResolutionOutcome.forbidden(
                self.resolver_id,
                "Validator rejected tenant access",
            )

        # Any non-bool truthy/falsy return (None, int, str, object…) → INTERNAL_ERROR.
        return TenantResolutionOutcome.internal_error(
            self.resolver_id,
            error=TypeError(
                f"Validator returned {type(result).__name__}, expected bool",
            ),
        )
