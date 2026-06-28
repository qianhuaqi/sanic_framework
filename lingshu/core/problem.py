"""Client-safe Problem Details construction."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from lingshu.core.errors import LingShuError, SafeValue
from lingshu.core.identifiers import RequestId

PROBLEM_MEDIA_TYPE = "application/problem+json"
_INTERNAL_CODE = "internal.error"
_INTERNAL_TITLE = "Internal Server Error"
_INTERNAL_DETAIL = "An internal error occurred."


def _thaw_safe_value(value: SafeValue) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_safe_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_safe_value(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class ProblemDetails:
    """Allowlisted RFC 9457-style client error document."""

    type: str
    title: str
    status: int
    detail: str
    code: str
    instance: str | None = None
    request_id: str | None = None
    details: Mapping[str, SafeValue] | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible allowlisted mapping."""

        document: dict[str, object] = {
            "type": self.type,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "code": self.code,
        }
        if self.instance is not None:
            document["instance"] = self.instance
        if self.request_id is not None:
            document["request_id"] = self.request_id
        if self.details:
            document["details"] = _thaw_safe_value(self.details)
        return document


def problem_from_exception(
    error: Exception,
    *,
    request_id: RequestId | None = None,
    instance: str | None = None,
) -> ProblemDetails:
    """Map an ordinary exception to client-safe Problem Details.

    Control-flow exceptions deriving directly from :class:`BaseException` are rejected rather
    than converted. Hidden framework failures and unexpected exceptions map to one generic
    ``internal.error`` document.
    """

    if not isinstance(error, Exception):
        raise TypeError("control-flow BaseException values must not be mapped as ordinary errors")

    request_text = str(request_id) if request_id is not None else None
    problem_instance = instance
    if problem_instance is None and request_text is not None:
        problem_instance = f"urn:lingshu:request:{request_text}"

    if isinstance(error, LingShuError) and error.client_visible:
        assert error.http_status is not None
        return ProblemDetails(
            type=f"urn:lingshu:error:{error.code}",
            title=error.title,
            status=error.http_status,
            detail=error.safe_message,
            code=error.code,
            instance=problem_instance,
            request_id=request_text,
            details=error.safe_details or None,
        )

    return ProblemDetails(
        type=f"urn:lingshu:error:{_INTERNAL_CODE}",
        title=_INTERNAL_TITLE,
        status=500,
        detail=_INTERNAL_DETAIL,
        code=_INTERNAL_CODE,
        instance=problem_instance,
        request_id=request_text,
    )


__all__ = ("PROBLEM_MEDIA_TYPE", "ProblemDetails", "problem_from_exception")
