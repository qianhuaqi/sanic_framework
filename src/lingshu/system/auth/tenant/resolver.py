from __future__ import annotations

from typing import Protocol, runtime_checkable

from lingshu.system.auth.tenant.context import TenantContext
from lingshu.system.auth.tenant.result import TenantResolutionOutcome, TenantResolutionResult


@runtime_checkable
class TenantResolver(Protocol):
    """Protocol for tenant resolvers.

    Each resolver receives the raw Sanic request and the authenticated
    Principal, and returns a :class:`TenantResolutionOutcome`.

    Implementations must:
    - Distinguish MISSING (no tenant identifier found) from MALFORMED
      (identifier present but invalid) and FORBIDDEN (identifier valid
      but access denied by the validator).
    - Never raise an exception for expected failure paths.
    - Never leak validator exceptions or internal details into
      ``error_description``.
    """

    resolver_id: str

    async def resolve(self, request, principal) -> TenantResolutionOutcome: ...


class TenantResolverChain:
    """Ordered registry of tenant resolvers and single-pass executor.

    Semantics:
    - Resolvers are executed in registration order.
    - The first SUCCESS short-circuits the chain.
    - MISSING does NOT short-circuit: a later resolver may succeed.
    - MALFORMED, FORBIDDEN, INTERNAL_ERROR immediately short-circuit.
    - If all resolvers return MISSING, the overall result is MISSING.
    - An empty chain returns MISSING.
    """

    def __init__(self):
        self._resolvers: list[TenantResolver] = []

    def register(self, resolver: TenantResolver) -> TenantResolver:
        if not hasattr(resolver, "resolver_id") or not resolver.resolver_id:
            raise ValueError("TenantResolver must have a non-empty resolver_id")
        if not isinstance(resolver.resolver_id, str):
            raise ValueError(
                f"TenantResolver.resolver_id must be str, got {type(resolver.resolver_id).__name__}"
            )
        if resolver.resolver_id != resolver.resolver_id.strip():
            raise ValueError(
                "TenantResolver.resolver_id must not have leading or trailing whitespace"
            )
        if any(r.resolver_id == resolver.resolver_id for r in self._resolvers):
            raise ValueError(
                f"Duplicate resolver_id: {resolver.resolver_id!r}"
            )
        self._resolvers.append(resolver)
        return resolver

    def get(self, resolver_id: str) -> TenantResolver | None:
        for r in self._resolvers:
            if r.resolver_id == resolver_id:
                return r
        return None

    @property
    def resolver_ids(self) -> tuple[str, ...]:
        return tuple(r.resolver_id for r in self._resolvers)

    @property
    def is_empty(self) -> bool:
        return len(self._resolvers) == 0

    async def resolve(self, request, principal) -> TenantResolutionOutcome:
        last_outcome: TenantResolutionOutcome | None = None

        for resolver in self._resolvers:
            try:
                outcome = await resolver.resolve(request, principal)
            except Exception as exc:
                outcome = TenantResolutionOutcome.internal_error(
                    resolver_id=getattr(resolver, "resolver_id", ""),
                    error=exc,
                )

            if outcome.is_success:
                return outcome

            if outcome.result is TenantResolutionResult.MISSING:
                last_outcome = outcome
                continue

            return outcome

        if last_outcome is not None:
            return last_outcome
        return TenantResolutionOutcome.missing()
