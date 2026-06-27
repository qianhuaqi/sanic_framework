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


def _validate_id(value: str, field_name: str) -> str:
    """Strict validation: must be a non-empty, non-whitespace string with no str() conversion."""
    if not isinstance(value, str):
        raise TypeError(f"TenantContext.{field_name} must be a str, got {type(value).__name__}")
    if not value:
        raise ValueError(f"TenantContext.{field_name} must not be empty")
    if value != value.strip():
        raise ValueError(f"TenantContext.{field_name} must not have leading or trailing whitespace")
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
        _validate_id(self.tenant_id, "tenant_id")
        _validate_id(self.resolver_id, "resolver_id")
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
        _validate_id(tenant_id, "tenant_id")
        _validate_id(resolver_id, "resolver_id")
        return cls(
            tenant_id=tenant_id,
            resolver_id=resolver_id,
            attributes=MappingProxyType(_deep_freeze(dict(attributes))) if attributes else MappingProxyType({}),
        )

    def __repr__(self) -> str:
        return f"TenantContext(tenant_id={self.tenant_id!r}, resolver_id={self.resolver_id!r})"
