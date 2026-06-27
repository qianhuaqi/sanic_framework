from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from lingshu.system.auth.tenant.context import TenantContext


class TenantResolutionResult(str, Enum):
    """Tenant resolution outcome taxonomy.

    Members:
        SUCCESS: Resolution succeeded; a TenantContext is attached.
        MISSING: No tenant identifier was found (does not short-circuit).
        MALFORMED: A tenant identifier was present but structurally invalid.
        FORBIDDEN: The tenant was identified but access was denied by the validator.
        INTERNAL_ERROR: An unexpected internal exception occurred.
    """

    SUCCESS = "success"
    MISSING = "missing"
    MALFORMED = "malformed"
    FORBIDDEN = "forbidden"
    INTERNAL_ERROR = "internal_error"

    @property
    def is_success(self) -> bool:
        return self is TenantResolutionResult.SUCCESS

    @property
    def is_failure(self) -> bool:
        return self is not TenantResolutionResult.SUCCESS

    @property
    def short_circuits(self) -> bool:
        """Whether this result stops the resolver chain.

        MISSING does NOT short-circuit (later resolvers may succeed).
        All other failure results immediately stop the chain.
        """
        return self is not TenantResolutionResult.MISSING


_RESULT_DEFAULT_MSG: dict[TenantResolutionResult, str] = {
    TenantResolutionResult.MISSING: "Tenant context is missing",
    TenantResolutionResult.MALFORMED: "Malformed tenant identifier",
    TenantResolutionResult.FORBIDDEN: "Tenant access forbidden",
    TenantResolutionResult.INTERNAL_ERROR: "Tenant resolver internal error",
}


@dataclass(frozen=True)
class TenantResolutionOutcome:
    """The result of a tenant resolution attempt.

    On success, ``tenant_context`` is populated.
    On failure, ``tenant_context`` is ``None`` and ``error_description`` is an
    internal-only diagnostic that must never reach a client response.
    """

    result: TenantResolutionResult
    tenant_context: TenantContext | None = None
    resolver_id: str = ""
    error_description: str = ""
    internal_error: BaseException | None = None

    @classmethod
    def success(cls, tenant_context: TenantContext) -> TenantResolutionOutcome:
        return cls(
            result=TenantResolutionResult.SUCCESS,
            tenant_context=tenant_context,
            resolver_id=tenant_context.resolver_id,
        )

    @classmethod
    def missing(cls, resolver_id: str = "") -> TenantResolutionOutcome:
        return cls(result=TenantResolutionResult.MISSING, resolver_id=resolver_id)

    @classmethod
    def malformed(cls, resolver_id: str = "", description: str = "") -> TenantResolutionOutcome:
        return cls(
            result=TenantResolutionResult.MALFORMED,
            resolver_id=resolver_id,
            error_description=description or "Tenant identifier is malformed",
        )

    @classmethod
    def forbidden(cls, resolver_id: str = "", description: str = "") -> TenantResolutionOutcome:
        return cls(
            result=TenantResolutionResult.FORBIDDEN,
            resolver_id=resolver_id,
            error_description=description or "Tenant access is forbidden",
        )

    @classmethod
    def internal_error(cls, resolver_id: str = "", error: BaseException | None = None) -> TenantResolutionOutcome:
        return cls(
            result=TenantResolutionResult.INTERNAL_ERROR,
            resolver_id=resolver_id,
            error_description="Tenant resolver internal error",
            internal_error=error,
        )

    @property
    def is_success(self) -> bool:
        return self.result.is_success

    def __repr__(self) -> str:
        return (
            f"TenantResolutionOutcome(result={self.result!r}, "
            f"tenant_context={'set' if self.tenant_context is not None else 'None'}, "
            f"resolver_id={self.resolver_id!r})"
        )
