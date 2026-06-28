"""Typed opaque identifiers and untrusted correlation validation."""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, Self

from lingshu.core.errors import FatalScope, InternalError, Severity

_LOWER_HEX_128 = re.compile(r"^[0-9a-f]{32}$")
_LOWER_HEX_256 = re.compile(r"^[0-9a-f]{64}$")
_EXTERNAL_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]+$")

type EntropySource = Callable[[int], bytes]


@dataclass(frozen=True, slots=True)
class _OpaqueId:
    value: str

    _pattern: ClassVar[re.Pattern[str]] = _LOWER_HEX_128
    _entropy_bytes: ClassVar[int] = 16

    def __post_init__(self) -> None:
        if self._pattern.fullmatch(self.value) is None:
            raise ValueError(f"{type(self).__name__} must use canonical lowercase hexadecimal")

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse a canonical identifier without changing its type."""

        return cls(value)

    @classmethod
    def generate(cls, entropy: EntropySource | None = None) -> Self:
        """Generate an unpredictable identifier using a secure source by default."""

        source = entropy or secrets.token_bytes
        try:
            raw = source(cls._entropy_bytes)
        except Exception as exc:
            raise InternalError(
                "internal.identifier_generation_failed",
                "Unable to generate an internal identifier.",
                title="Internal identifier generation failed",
                severity=Severity.CRITICAL,
                fatal_scope=FatalScope.OPERATION,
                cause=exc,
            ) from exc

        if not isinstance(raw, bytes) or len(raw) != cls._entropy_bytes:
            cause = ValueError("entropy source returned an invalid byte sequence")
            raise InternalError(
                "internal.identifier_generation_failed",
                "Unable to generate an internal identifier.",
                title="Internal identifier generation failed",
                severity=Severity.CRITICAL,
                fatal_scope=FatalScope.OPERATION,
                cause=cause,
            ) from cause
        return cls(raw.hex())

    def __str__(self) -> str:
        return self.value


class RequestId(_OpaqueId):
    """Internal request identifier."""


class ConnectionId(_OpaqueId):
    """Internal connection identifier."""


class TraceId(_OpaqueId):
    """Trace-correlation identifier; never an authorization credential."""


class OperationId(_OpaqueId):
    """Internal operation identifier."""


class WorkerId(_OpaqueId):
    """Internal Worker identifier."""


class RecordId(_OpaqueId):
    """Internal Runtime Record identifier."""


@dataclass(frozen=True, slots=True)
class RevisionId:
    """SHA-256 identity of canonical validated Application Revision bytes."""

    value: str

    def __post_init__(self) -> None:
        if _LOWER_HEX_256.fullmatch(self.value) is None:
            message = "RevisionId must be a 64-character lowercase SHA-256 hexadecimal value"
            raise ValueError(message)

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse a canonical RevisionId."""

        return cls(value)

    @classmethod
    def from_canonical_bytes(cls, value: bytes) -> Self:
        """Hash canonical validated Revision bytes."""

        return cls(hashlib.sha256(value).hexdigest())

    def __str__(self) -> str:
        return self.value


def validate_external_request_id(value: str, *, max_length: int = 128) -> str:
    """Validate an untrusted external request-correlation value.

    The returned string remains external metadata. It must never replace a generated
    :class:`RequestId`.
    """

    if not 1 <= max_length <= 1024:
        raise ValueError("max_length must be between 1 and 1024")
    if not value or len(value) > max_length:
        raise ValueError("external request ID length is outside the allowed bound")
    if _EXTERNAL_REQUEST_ID.fullmatch(value) is None:
        raise ValueError("external request ID contains unsupported characters")
    return value


__all__ = (
    "ConnectionId",
    "EntropySource",
    "OperationId",
    "RecordId",
    "RequestId",
    "RevisionId",
    "TraceId",
    "WorkerId",
    "validate_external_request_id",
)
