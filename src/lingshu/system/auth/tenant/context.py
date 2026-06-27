from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        return MappingProxyType({k: _deep_freeze(v) for k, v in value.items()})
    if isinstance(value, dict):
        return MappingProxyType({k: _deep_freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_deep_freeze(item) for item in value)
    if isinstance(value, frozenset):
        return value
    return value


@dataclass(frozen=True)
class TenantContext:
    """Immutable tenant context produced by a TenantResolver.

    Attributes:
        tenant_id: Stable, non-empty string identifying the tenant.
        resolver_id: Name of the resolver that produced this context.
        attributes: Deep-frozen, read-only mapping of verified attributes.
    """

    tenant_id: str
    resolver_id: str
    attributes: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self):
        if not isinstance(self.tenant_id, str) or not self.tenant_id:
            raise ValueError("TenantContext.tenant_id must be a non-empty string")
        if not isinstance(self.resolver_id, str) or not self.resolver_id:
            raise ValueError("TenantContext.resolver_id must be a non-empty string")
        if not isinstance(self.attributes, MappingProxyType):
            raise TypeError("TenantContext.attributes must be a MappingProxyType")

    @classmethod
    def create(
        cls,
        tenant_id: str,
        resolver_id: str,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> TenantContext:
        """Create a TenantContext with deep-frozen attributes."""
        return cls(
            tenant_id=str(tenant_id),
            resolver_id=str(resolver_id),
            attributes=MappingProxyType(_deep_freeze(dict(attributes))) if attributes else MappingProxyType({}),
        )

    def __repr__(self) -> str:
        return f"TenantContext(tenant_id={self.tenant_id!r}, resolver_id={self.resolver_id!r})"
