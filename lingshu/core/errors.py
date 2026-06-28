"""Stable framework error contracts and safe-detail validation."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

_ERROR_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")

type SafeScalar = str | int | float | bool | None
type SafeValue = SafeScalar | tuple[SafeValue, ...] | Mapping[str, SafeValue]
type SafeDetails = Mapping[str, SafeValue]


class Severity(StrEnum):
    """Bounded framework-event severity."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class FatalScope(StrEnum):
    """Smallest ownership scope that must fail for an error."""

    OPERATION = "operation"
    REQUEST = "request"
    CONNECTION = "connection"
    WORKER = "worker"
    SUPERVISOR = "supervisor"


def validate_error_code(code: str) -> str:
    """Validate and return a stable lowercase dotted error code."""

    if _ERROR_CODE_PATTERN.fullmatch(code) is None:
        raise ValueError("error code must be a lowercase dotted identifier")
    return code


def freeze_safe_value(value: object) -> SafeValue:
    """Validate and recursively freeze an allowlisted client-safe value.

    Mappings become read-only mapping proxies and sequences become tuples. Arbitrary objects,
    non-string keys, bytes, and non-finite floats are rejected.
    """

    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("safe details cannot contain non-finite floats")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, SafeValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("safe detail mapping keys must be strings")
            frozen[key] = freeze_safe_value(item)
        return MappingProxyType(frozen)
    if isinstance(value, list | tuple):
        return tuple(freeze_safe_value(item) for item in value)
    raise TypeError(f"unsupported safe detail value type: {type(value).__name__}")


def freeze_safe_details(details: Mapping[str, object] | None) -> SafeDetails:
    """Validate and freeze a top-level safe-details mapping."""

    if details is None:
        return MappingProxyType({})

    frozen = freeze_safe_value(details)
    if not isinstance(frozen, Mapping):
        raise TypeError("safe details must be a mapping")
    return frozen


class LingShuError(Exception):
    """Root of ordinary LingShu framework failures.

    ``safe_message`` and ``safe_details`` are the only error-provided values eligible for a
    client response. ``internal_cause`` is retained for internal diagnostics and is never
    serialized automatically.
    """

    def __init__(
        self,
        code: str,
        safe_message: str,
        *,
        title: str | None = None,
        client_visible: bool = False,
        retryable: bool = False,
        http_status: int | None = None,
        severity: Severity = Severity.ERROR,
        fatal_scope: FatalScope = FatalScope.OPERATION,
        safe_details: Mapping[str, object] | None = None,
        cause: Exception | None = None,
    ) -> None:
        if not safe_message:
            raise ValueError("safe_message must not be empty")
        if title is not None and not title:
            raise ValueError("title must not be empty")
        if http_status is not None and not 400 <= http_status <= 599:
            raise ValueError("http_status must be between 400 and 599")
        if client_visible and http_status is None:
            raise ValueError("client-visible errors require an HTTP status")

        self.code = validate_error_code(code)
        self.safe_message = safe_message
        self.title = title or safe_message
        self.client_visible = client_visible
        self.retryable = retryable
        self.http_status = http_status
        self.severity = severity
        self.fatal_scope = fatal_scope
        self.safe_details = freeze_safe_details(safe_details)
        self.internal_cause = cause
        super().__init__(safe_message)
        if cause is not None:
            self.__cause__ = cause


class ConfigurationError(LingShuError):
    """Configuration loading or validation failure."""


class LifecycleError(LingShuError):
    """Invalid application or resource lifecycle transition."""


class ProtocolError(LingShuError):
    """Malformed, ambiguous, or unsupported protocol input."""


class RequestError(LingShuError):
    """Invalid or unsatisfied request contract."""


class RoutingError(LingShuError):
    """Route registration or matching failure."""


class HandlerContractError(LingShuError):
    """Handler signature or return-contract failure."""


class SerializationError(LingShuError):
    """Serialization or deserialization failure."""


class ResourceLimitError(LingShuError):
    """A bounded resource limit has been reached."""


class AdmissionError(LingShuError):
    """Work was rejected by admission control."""


class DeadlineError(LingShuError):
    """An operation exhausted its absolute deadline budget."""


class ExtensionError(LingShuError):
    """Extension registration, startup, or execution failure."""


class RecordError(LingShuError):
    """Runtime Record reservation or event failure."""


class StorageError(LingShuError):
    """Framework storage failure."""


class InternalError(LingShuError):
    """Unexpected or invariant-breaking internal framework failure."""


__all__ = (
    "AdmissionError",
    "ConfigurationError",
    "DeadlineError",
    "ExtensionError",
    "FatalScope",
    "HandlerContractError",
    "InternalError",
    "LifecycleError",
    "LingShuError",
    "ProtocolError",
    "RecordError",
    "RequestError",
    "ResourceLimitError",
    "RoutingError",
    "SafeDetails",
    "SafeScalar",
    "SafeValue",
    "SerializationError",
    "Severity",
    "StorageError",
    "freeze_safe_details",
    "freeze_safe_value",
    "validate_error_code",
)
