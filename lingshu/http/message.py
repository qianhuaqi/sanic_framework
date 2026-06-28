"""Immutable HTTP value objects and bounded header normalization."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum

from lingshu.core.errors import FatalScope, ProtocolError, ResourceLimitError

_TOKEN = re.compile(rb"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_METHOD = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


class HTTPVersion(StrEnum):
    """Supported P1 protocol versions."""

    HTTP_1_0 = "HTTP/1.0"
    HTTP_1_1 = "HTTP/1.1"


@dataclass(frozen=True, slots=True)
class HTTPMethod:
    """Canonical uppercase HTTP method token."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.upper()
        if _METHOD.fullmatch(normalized) is None:
            raise ProtocolError(
                "protocol.invalid_method",
                "The HTTP method is invalid.",
                fatal_scope=FatalScope.CONNECTION,
            )
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class RequestTarget:
    """Origin-form request target split into immutable path and query text."""

    raw: str
    path: str
    query: str

    @classmethod
    def parse(cls, raw: str, *, max_bytes: int = 8192) -> RequestTarget:
        """Parse the P1 origin-form request-target subset."""

        if not isinstance(raw, str):
            raise TypeError("request target must be a string")
        if max_bytes <= 0:
            raise ValueError("request target limit must be positive")
        try:
            encoded = raw.encode("ascii", "strict")
        except UnicodeEncodeError as exc:
            raise ProtocolError(
                "protocol.invalid_target",
                "The request target is invalid.",
                fatal_scope=FatalScope.CONNECTION,
                cause=exc,
            ) from exc
        if not encoded or len(encoded) > max_bytes:
            raise ResourceLimitError(
                "request.target_too_large",
                "The request target exceeds the configured limit.",
                fatal_scope=FatalScope.CONNECTION,
                safe_details={"limit": max_bytes},
            )
        if not raw.startswith("/") or "#" in raw or "\x00" in raw:
            raise ProtocolError(
                "protocol.invalid_target",
                "The request target is invalid.",
                fatal_scope=FatalScope.CONNECTION,
            )
        path, separator, query = raw.partition("?")
        return cls(raw=raw, path=path, query=query if separator else "")


class Headers:
    """Immutable duplicate-preserving, case-insensitive HTTP headers."""

    __slots__ = ("_items", "_lookup", "_total_bytes")

    def __init__(
        self,
        items: Iterable[tuple[str | bytes, str | bytes]] = (),
        *,
        max_fields: int = 100,
        max_name_bytes: int = 256,
        max_value_bytes: int = 8192,
        max_total_bytes: int = 65536,
    ) -> None:
        if min(max_fields, max_name_bytes, max_value_bytes, max_total_bytes) <= 0:
            raise ValueError("header limits must be positive")
        normalized: list[tuple[str, str]] = []
        lookup: dict[str, list[str]] = {}
        total = 0
        for raw_name, raw_value in items:
            if len(normalized) >= max_fields:
                raise ResourceLimitError(
                    "request.headers_too_many",
                    "The request has too many header fields.",
                    fatal_scope=FatalScope.CONNECTION,
                    safe_details={"limit": max_fields},
                )
            name_bytes = _as_latin1_bytes(raw_name, "header name")
            value_bytes = _as_latin1_bytes(raw_value, "header value")
            if len(name_bytes) > max_name_bytes or len(value_bytes) > max_value_bytes:
                raise ResourceLimitError(
                    "request.header_too_large",
                    "An HTTP header exceeds the configured limit.",
                    fatal_scope=FatalScope.CONNECTION,
                )
            if _TOKEN.fullmatch(name_bytes) is None:
                raise ProtocolError(
                    "protocol.invalid_header_name",
                    "An HTTP header name is invalid.",
                    fatal_scope=FatalScope.CONNECTION,
                )
            if _contains_invalid_value_byte(value_bytes):
                raise ProtocolError(
                    "protocol.invalid_header_value",
                    "An HTTP header value is invalid.",
                    fatal_scope=FatalScope.CONNECTION,
                )
            name = name_bytes.decode("ascii").lower()
            value = value_bytes.decode("latin-1").strip(" \t")
            total += len(name_bytes) + len(value_bytes)
            if total > max_total_bytes:
                raise ResourceLimitError(
                    "request.headers_too_large",
                    "The HTTP headers exceed the configured limit.",
                    fatal_scope=FatalScope.CONNECTION,
                    safe_details={"limit": max_total_bytes},
                )
            normalized.append((name, value))
            lookup.setdefault(name, []).append(value)
        self._items = tuple(normalized)
        self._lookup = {name: tuple(values) for name, values in lookup.items()}
        self._total_bytes = total

    @property
    def total_bytes(self) -> int:
        return self._total_bytes

    def get(self, name: str, default: str | None = None) -> str | None:
        values = self._lookup.get(_normalize_lookup_name(name))
        return values[-1] if values else default

    def get_all(self, name: str) -> tuple[str, ...]:
        return self._lookup.get(_normalize_lookup_name(name), ())

    def contains(self, name: str) -> bool:
        return _normalize_lookup_name(name) in self._lookup

    def items(self) -> tuple[tuple[str, str], ...]:
        return self._items

    def __iter__(self) -> Iterator[tuple[str, str]]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __repr__(self) -> str:
        return f"Headers(fields={len(self._items)}, total_bytes={self._total_bytes})"


def _as_latin1_bytes(value: str | bytes, label: str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        try:
            return value.encode("latin-1")
        except UnicodeEncodeError as exc:
            raise ProtocolError(
                "protocol.invalid_header_value",
                f"The {label} is not representable in HTTP/1.1.",
                fatal_scope=FatalScope.CONNECTION,
                cause=exc,
            ) from exc
    raise TypeError(f"{label} must be str or bytes")


def _contains_invalid_value_byte(value: bytes) -> bool:
    return any(byte == 0x7F or (byte < 0x20 and byte != 0x09) for byte in value)


def _normalize_lookup_name(name: str) -> str:
    try:
        encoded = name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("header lookup name must be ASCII") from exc
    if _TOKEN.fullmatch(encoded) is None:
        raise ValueError("invalid header lookup name")
    return name.lower()


__all__ = ("HTTPMethod", "HTTPVersion", "Headers", "RequestTarget")
