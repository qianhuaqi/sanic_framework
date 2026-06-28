"""Scoped immutable HTTP Request metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from lingshu.core.errors import FatalScope, RequestError
from lingshu.core.identifiers import ConnectionId, RequestId, TraceId
from lingshu.http.body import RequestBody
from lingshu.http.message import Headers, HTTPMethod, HTTPVersion, RequestTarget
from lingshu.runtime import Scope, ScopeState


@dataclass(frozen=True, slots=True)
class ConnectionInfo:
    """Safe immutable connection metadata attached to one Request."""

    peer: str | None = None
    local: str | None = None
    secure: bool = False


class Request:
    """Request-scoped immutable metadata with explicit mutable application state."""

    __slots__ = (
        "_authority",
        "_body",
        "_connection_id",
        "_connection_info",
        "_headers",
        "_method",
        "_path_params",
        "_request_id",
        "_route_name",
        "_scheme",
        "_scope",
        "_state",
        "_target",
        "_trace_id",
        "_version",
    )

    def __init__(
        self,
        *,
        method: HTTPMethod,
        target: RequestTarget,
        version: HTTPVersion,
        headers: Headers,
        scope: Scope,
        body: RequestBody,
        request_id: RequestId,
        connection_id: ConnectionId,
        trace_id: TraceId | None = None,
        scheme: str = "http",
        authority: str | None = None,
        connection_info: ConnectionInfo | None = None,
    ) -> None:
        if scheme not in {"http", "https"}:
            raise ValueError("scheme must be http or https")
        self._method = method
        self._target = target
        self._version = version
        self._headers = headers
        self._scope = scope
        self._body = body
        self._request_id = request_id
        self._connection_id = connection_id
        self._trace_id = trace_id
        self._scheme = scheme
        self._authority = authority
        self._connection_info = connection_info or ConnectionInfo()
        self._state: dict[object, object] = {}
        self._route_name: str | None = None
        self._path_params: Mapping[str, str] = MappingProxyType({})

    @property
    def method(self) -> HTTPMethod:
        self._ensure_active()
        return self._method

    @property
    def target(self) -> RequestTarget:
        self._ensure_active()
        return self._target

    @property
    def path(self) -> str:
        self._ensure_active()
        return self._target.path

    @property
    def query(self) -> str:
        self._ensure_active()
        return self._target.query

    @property
    def version(self) -> HTTPVersion:
        self._ensure_active()
        return self._version

    @property
    def headers(self) -> Headers:
        self._ensure_active()
        return self._headers

    @property
    def body(self) -> RequestBody:
        self._ensure_active()
        return self._body

    @property
    def request_id(self) -> RequestId:
        self._ensure_active()
        return self._request_id

    @property
    def connection_id(self) -> ConnectionId:
        self._ensure_active()
        return self._connection_id

    @property
    def trace_id(self) -> TraceId | None:
        self._ensure_active()
        return self._trace_id

    @property
    def scheme(self) -> str:
        self._ensure_active()
        return self._scheme

    @property
    def authority(self) -> str | None:
        self._ensure_active()
        return self._authority

    @property
    def connection_info(self) -> ConnectionInfo:
        self._ensure_active()
        return self._connection_info

    @property
    def state(self) -> dict[object, object]:
        self._ensure_active()
        return self._state

    @property
    def route_name(self) -> str | None:
        self._ensure_active()
        return self._route_name

    @property
    def path_params(self) -> Mapping[str, str]:
        self._ensure_active()
        return self._path_params

    def publish_route(self, route_name: str, path_params: Mapping[str, str]) -> None:
        """Publish route metadata exactly once after a successful match."""

        self._ensure_active()
        if self._route_name is not None:
            raise RequestError(
                "request.route_already_published",
                "Route metadata has already been published.",
                fatal_scope=FatalScope.REQUEST,
            )
        if not route_name:
            raise ValueError("route name must not be empty")
        frozen: dict[str, str] = {}
        for key, value in path_params.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise TypeError("path parameters must be string pairs")
            frozen[key] = value
        self._route_name = route_name
        self._path_params = MappingProxyType(frozen)

    def _ensure_active(self) -> None:
        if self._scope.state is ScopeState.CLOSED:
            raise RequestError(
                "request.scope_closed",
                "The request Scope is closed.",
                fatal_scope=FatalScope.REQUEST,
            )
        self._scope.checkpoint()


__all__ = ("ConnectionInfo", "Request")
