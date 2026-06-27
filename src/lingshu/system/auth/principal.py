from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


def _deep_freeze(value: Any) -> Any:
    """Recursively freeze a value so that all nested containers are immutable."""
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


def _validate_scopes(scopes: Any) -> frozenset[str]:
    """Validate that every scope is a non-empty string."""
    if scopes is None:
        return frozenset()
    result: set[str] = set()
    for item in scopes:
        if not isinstance(item, str):
            raise TypeError(f"Scope must be a string, got {type(item).__name__}")
        stripped = item.strip()
        if not stripped:
            raise ValueError("Scope must be a non-empty string")
        result.add(stripped)
    return frozenset(result)


@dataclass(frozen=True)
class Principal:
    """Immutable authenticated identity.

    The Principal carries only identity-level data.  It deliberately does NOT
    resolve or store tenant information — tenant trust is a later phase.

    Attributes:
        subject: Stable identifier for the authenticated party (e.g. user id).
        authenticator_id: Name of the authenticator that produced this principal.
        scopes: Frozen set of non-empty string scopes.
        claims: Deep-frozen mapping of verified JWT/custom claims.
    """

    subject: str
    authenticator_id: str
    scopes: frozenset[str] = field(default_factory=frozenset)
    claims: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self):
        if not isinstance(self.subject, str) or not self.subject:
            raise ValueError("Principal.subject must be a non-empty string")
        if not isinstance(self.authenticator_id, str) or not self.authenticator_id:
            raise ValueError("Principal.authenticator_id must be a non-empty string")
        if not isinstance(self.scopes, frozenset):
            raise TypeError("Principal.scopes must be a frozenset")
        if not isinstance(self.claims, MappingProxyType):
            raise TypeError("Principal.claims must be a MappingProxyType")

    @classmethod
    def create(
        cls,
        subject: str,
        authenticator_id: str,
        *,
        scopes: frozenset[str] | set[str] | tuple[str, ...] | list[str] | None = None,
        claims: dict[str, Any] | None = None,
    ) -> Principal:
        """Create a Principal with deep-frozen scopes, claims, and nested values."""
        return cls(
            subject=str(subject),
            authenticator_id=str(authenticator_id),
            scopes=_validate_scopes(scopes),
            claims=MappingProxyType(_deep_freeze(dict(claims))) if claims else MappingProxyType({}),
        )

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def __repr__(self) -> str:
        return f"Principal(subject={self.subject!r}, authenticator_id={self.authenticator_id!r})"
