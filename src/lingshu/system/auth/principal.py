from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class Principal:
    """Immutable authenticated identity.

    The Principal carries only identity-level data.  It deliberately does NOT
    resolve or store tenant information — tenant trust is a later phase.

    Attributes:
        subject: Stable identifier for the authenticated party (e.g. user id).
        authenticator_id: Name of the authenticator that produced this principal.
        scopes: Frozen set of scope strings.  Authorization checks are out of
            scope for C2.1; scopes are exposed read-only for future use.
        claims: Frozen mapping of verified JWT/custom claims.  Only claims that
            were cryptographically verified by the authenticator belong here.
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
        scopes: frozenset[str] | set[str] | tuple[str, ...] | None = None,
        claims: dict[str, Any] | None = None,
    ) -> Principal:
        """Create a Principal with frozen scopes and read-only claims."""
        return cls(
            subject=str(subject),
            authenticator_id=str(authenticator_id),
            scopes=frozenset(scopes) if scopes is not None else frozenset(),
            claims=MappingProxyType(dict(claims)) if claims else MappingProxyType({}),
        )

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def __repr__(self) -> str:
        # Deliberately omit claims and scopes detail to avoid accidental
        # leakage in logs.  subject and authenticator_id are structural.
        return f"Principal(subject={self.subject!r}, authenticator_id={self.authenticator_id!r})"
