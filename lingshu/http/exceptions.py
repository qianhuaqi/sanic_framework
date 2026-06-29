"""Intentional application-level HTTP exception."""

from __future__ import annotations

from types import MappingProxyType

from lingshu.core.errors import FatalScope, LingShuError

_DEFAULT_DETAIL: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    410: "Gone",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}


class HTTPException(LingShuError):
    """Intentional client-visible HTTP exception.

    Raised inside a handler or middleware to produce an error response with an explicit
    HTTP status code. Only safe, client-visible information is stored: cause, traceback,
    file paths, secrets, and request bodies are never retained.

    The ``headers`` mapping, if provided, is frozen into an immutable proxy at construction.
    """

    __slots__ = ("_headers", "_status_code")

    def __init__(
        self,
        status_code: int,
        detail: str = "",
        *,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        if not isinstance(status_code, int) or isinstance(status_code, bool):
            raise ValueError("HTTPException status_code must be an integer")
        if not 400 <= status_code <= 599:
            raise ValueError("HTTPException status_code must be between 400 and 599")
        resolved_detail = detail or _DEFAULT_DETAIL.get(status_code, "HTTP Error")
        resolved_code = code or f"http.status_{status_code}"
        super().__init__(
            resolved_code,
            resolved_detail,
            title=resolved_detail,
            client_visible=True,
            http_status=status_code,
            fatal_scope=FatalScope.REQUEST,
        )
        self._status_code = status_code
        self._headers = (
            MappingProxyType(dict(headers)) if headers else MappingProxyType({})
        )

    @property
    def status_code(self) -> int:
        return self._status_code

    @property
    def headers(self) -> MappingProxyType[str, str]:
        return self._headers


__all__ = ("HTTPException",)
