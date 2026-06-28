"""Buffered Response factories, normalization, and commit state."""

from __future__ import annotations

import builtins
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from lingshu.core.errors import FatalScope, HandlerContractError, LifecycleError
from lingshu.http.message import Headers


class ResponseState(StrEnum):
    """P1 buffered Response lifecycle."""

    ABORTED = "aborted"
    COMMITTED = "committed"
    COMPLETED = "completed"
    NEW = "new"
    PREPARED = "prepared"


@dataclass(frozen=True, slots=True)
class ResponseHead:
    """Immutable finalized response head accepted by a future Transport."""

    status: int
    headers: Headers


class Response:
    """Buffered P1 Response with exactly-once head commit."""

    __slots__ = (
        "_auto_content_length",
        "_body",
        "_headers",
        "_normalized",
        "_state",
        "_status",
    )

    def __init__(
        self,
        body: bytes = b"",
        *,
        status: int = 200,
        headers: Iterable[tuple[str | bytes, str | bytes]] = (),
    ) -> None:
        _validate_status(status)
        self._status = status
        self._headers = list(Headers(headers).items())
        self._body = bytes(body)
        self._state = ResponseState.NEW
        self._normalized = False
        self._auto_content_length = False

    @classmethod
    def text(
        cls,
        text: str,
        *,
        status: int = 200,
        headers: Iterable[tuple[str | bytes, str | bytes]] = (),
    ) -> Response:
        """Create a UTF-8 text response with an explicit media type."""

        response = cls(text.encode("utf-8"), status=status, headers=headers)
        if not response._has_header("content-type"):
            response._headers.append(("content-type", "text/plain; charset=utf-8"))
        return response

    @classmethod
    def bytes(
        cls,
        value: bytes | bytearray | memoryview,
        *,
        status: int = 200,
        headers: Iterable[tuple[str | bytes, str | bytes]] = (),
    ) -> Response:
        """Create an octet-stream response from bytes-like input."""

        response = cls(bytes(value), status=status, headers=headers)
        if not response._has_header("content-type"):
            response._headers.append(("content-type", "application/octet-stream"))
        return response

    @property
    def state(self) -> ResponseState:
        return self._state

    @property
    def status(self) -> int:
        return self._status

    @status.setter
    def status(self, value: int) -> None:
        self._ensure_mutable()
        _validate_status(value)
        self._status = value

    @property
    def headers(self) -> Headers:
        return Headers(self._headers)

    @property
    def body(self) -> builtins.bytes:
        return self._body

    def set_header(
        self,
        name: str | builtins.bytes,
        value: str | builtins.bytes,
    ) -> None:
        """Replace all fields with ``name`` before commit."""

        self._ensure_mutable()
        item = Headers(((name, value),)).items()[0]
        normalized_name = item[0]
        self._headers = [entry for entry in self._headers if entry[0] != normalized_name]
        self._headers.append(item)
        if normalized_name == "content-length":
            self._auto_content_length = False

    def add_header(
        self,
        name: str | builtins.bytes,
        value: str | builtins.bytes,
    ) -> None:
        """Append a duplicate-preserving field before commit."""

        self._ensure_mutable()
        item = Headers(((name, value),)).items()[0]
        self._headers.append(item)
        if item[0] == "content-length":
            self._auto_content_length = False

    def write(self, value: builtins.bytes | bytearray | memoryview) -> None:
        """Append buffered bytes before commit.

        This is not the deferred public streaming-response API.
        """

        self._ensure_mutable()
        self._body += bytes(value)

    def prepare(self) -> ResponseHead:
        """Finalize a replaceable head without committing it to Transport."""

        if self._state is ResponseState.NEW:
            if not self._has_header("content-length"):
                self._headers.append(("content-length", str(len(self._body))))
                self._auto_content_length = True
            self._state = ResponseState.PREPARED
        elif self._state is not ResponseState.PREPARED:
            raise _response_state_error("Response cannot be prepared in its current state.")
        return ResponseHead(self._status, Headers(self._headers))

    def commit(self) -> ResponseHead:
        """Commit the finalized response head exactly once."""

        if self._state is ResponseState.NEW:
            head = self.prepare()
        elif self._state is ResponseState.PREPARED:
            head = ResponseHead(self._status, Headers(self._headers))
        else:
            raise _response_state_error("Response head can be committed only once.")
        self._state = ResponseState.COMMITTED
        return head

    def complete(self) -> None:
        """Mark successful body transmission complete."""

        if self._state is not ResponseState.COMMITTED:
            raise _response_state_error("Only a committed Response can complete.")
        self._state = ResponseState.COMPLETED

    def abort(self) -> bool:
        """Abort before completion and report whether state changed."""

        if self._state is ResponseState.ABORTED:
            return False
        if self._state is ResponseState.COMPLETED:
            raise _response_state_error("A completed Response cannot be aborted.")
        self._state = ResponseState.ABORTED
        return True

    def _mark_normalized(self) -> None:
        if self._normalized:
            raise HandlerContractError(
                "handler.return_already_normalized",
                "The Handler return value was normalized more than once.",
                fatal_scope=FatalScope.REQUEST,
            )
        self._normalized = True

    def _ensure_mutable(self) -> None:
        if self._state not in {ResponseState.NEW, ResponseState.PREPARED}:
            raise _response_state_error("Response mutation is not allowed after commit.")
        if self._state is ResponseState.PREPARED:
            if self._auto_content_length:
                self._headers = [item for item in self._headers if item[0] != "content-length"]
                self._auto_content_length = False
            self._state = ResponseState.NEW

    def _has_header(self, name: str) -> bool:
        normalized = name.lower()
        return any(item_name == normalized for item_name, _ in self._headers)


type SupportedReturnValue = Response | str | bytes | bytearray | memoryview


def normalize_response(value: object) -> Response:
    """Normalize the frozen P1 Handler return set exactly once."""

    if isinstance(value, Response):
        response = value
    elif isinstance(value, str):
        response = Response.text(value)
    elif isinstance(value, bytes | bytearray | memoryview):
        response = Response.bytes(value)
    else:
        raise HandlerContractError(
            "handler.invalid_return",
            "The Handler returned an unsupported value.",
            fatal_scope=FatalScope.REQUEST,
            safe_details={"allowed": ("Response", "str", "bytes-like")},
        )
    response._mark_normalized()
    return response


def _validate_status(status: int) -> None:
    if isinstance(status, bool) or not isinstance(status, int) or not 100 <= status <= 599:
        raise ValueError("HTTP status must be an integer between 100 and 599")


def _response_state_error(message: str) -> LifecycleError:
    return LifecycleError(
        "response.invalid_state",
        message,
        fatal_scope=FatalScope.REQUEST,
    )


__all__ = (
    "Response",
    "ResponseHead",
    "ResponseState",
    "SupportedReturnValue",
    "normalize_response",
)
