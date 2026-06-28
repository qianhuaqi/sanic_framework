"""Immutable deterministic route declarations and matcher."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from lingshu.core.errors import FatalScope, ProtocolError, RoutingError
from lingshu.http.message import HTTPMethod
from lingshu.http.middleware import MiddlewareDeclaration
from lingshu.http.request import Request
from lingshu.http.response import SupportedReturnValue

_PARAMETER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

type Handler = Callable[[Request], Awaitable[SupportedReturnValue]]


class RouteMatchKind(StrEnum):
    """Exhaustive route matching outcomes."""

    MATCH = "match"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class _Segment:
    literal: str | None = None
    parameter: str | None = None


@dataclass(frozen=True, slots=True, init=False)
class RouteDeclaration:
    """Immutable route declaration consumed by the future Application freeze."""

    path_template: str
    methods: tuple[HTTPMethod, ...]
    handler: Handler
    name: str | None
    route_middleware: tuple[MiddlewareDeclaration, ...]
    _segments: tuple[_Segment, ...]

    def __init__(
        self,
        path_template: str,
        methods: Iterable[str | HTTPMethod],
        handler: Handler,
        *,
        name: str | None = None,
        route_middleware: Iterable[MiddlewareDeclaration] = (),
    ) -> None:
        segments = _parse_template(path_template)
        normalized_methods = _normalize_methods(methods)
        if not callable(handler):
            raise _routing_error(
                "routing.invalid_handler",
                "A route handler must be callable.",
            )
        if name is not None and not name:
            raise _routing_error(
                "routing.invalid_name",
                "A route name must not be empty.",
            )
        middleware = tuple(route_middleware)
        if any(not isinstance(item, MiddlewareDeclaration) for item in middleware):
            raise TypeError(
                "route_middleware must contain MiddlewareDeclaration values"
            )

        object.__setattr__(self, "path_template", path_template)
        object.__setattr__(self, "methods", normalized_methods)
        object.__setattr__(self, "handler", handler)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "route_middleware", middleware)
        object.__setattr__(self, "_segments", segments)

    @property
    def identity(self) -> tuple[str, tuple[str, ...]]:
        """Stable registration identity independent of object identity."""

        return self.path_template, tuple(method.value for method in self.methods)

    def __repr__(self) -> str:
        methods = ",".join(method.value for method in self.methods)
        return f"RouteDeclaration(path_template={self.path_template!r}, methods={methods!r})"


@dataclass(frozen=True, slots=True)
class RouteMatch:
    """Immutable selected-route, 404, or 405 outcome."""

    kind: RouteMatchKind
    route: RouteDeclaration | None
    path_params: Mapping[str, str]
    allowed_methods: tuple[HTTPMethod, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "path_params", MappingProxyType(dict(self.path_params))
        )
        object.__setattr__(self, "allowed_methods", tuple(self.allowed_methods))
        if self.kind is RouteMatchKind.MATCH:
            if self.route is None or self.allowed_methods:
                raise ValueError("matched route outcome is inconsistent")
        elif self.kind is RouteMatchKind.METHOD_NOT_ALLOWED:
            if self.route is not None or self.path_params or not self.allowed_methods:
                raise ValueError("method-not-allowed outcome is inconsistent")
        elif self.route is not None or self.path_params or self.allowed_methods:
            raise ValueError("not-found outcome is inconsistent")

    @classmethod
    def matched(
        cls,
        route: RouteDeclaration,
        path_params: Mapping[str, str],
    ) -> RouteMatch:
        return cls(
            RouteMatchKind.MATCH,
            route,
            MappingProxyType(dict(path_params)),
            (),
        )

    @classmethod
    def not_found(cls) -> RouteMatch:
        return cls(RouteMatchKind.NOT_FOUND, None, MappingProxyType({}), ())

    @classmethod
    def method_not_allowed(
        cls,
        allowed_methods: Iterable[HTTPMethod],
    ) -> RouteMatch:
        unique = {method.value: method for method in allowed_methods}
        methods = tuple(unique[value] for value in sorted(unique))
        return cls(
            RouteMatchKind.METHOD_NOT_ALLOWED,
            None,
            MappingProxyType({}),
            methods,
        )


@dataclass(frozen=True, slots=True)
class _RouteGroup:
    shape: tuple[tuple[str, str], ...]
    specificity: tuple[int, ...]
    routes_by_method: Mapping[str, RouteDeclaration]

    def capture(
        self, route: RouteDeclaration, values: tuple[str, ...]
    ) -> Mapping[str, str]:
        params: dict[str, str] = {}
        for segment, value in zip(route._segments, values, strict=True):
            if segment.parameter is not None:
                params[segment.parameter] = value
        return MappingProxyType(params)


@dataclass(frozen=True, slots=True, init=False)
class Router:
    """Immutable matcher compiled from validated route declarations."""

    _routes: tuple[RouteDeclaration, ...]
    _groups: tuple[_RouteGroup, ...]
    _named: Mapping[str, RouteDeclaration]

    def __init__(
        self,
        routes: tuple[RouteDeclaration, ...],
        groups: tuple[_RouteGroup, ...],
        named: Mapping[str, RouteDeclaration],
    ) -> None:
        object.__setattr__(self, "_routes", routes)
        object.__setattr__(self, "_groups", groups)
        object.__setattr__(self, "_named", MappingProxyType(dict(named)))

    @property
    def routes(self) -> tuple[RouteDeclaration, ...]:
        return self._routes

    def get_named(self, name: str) -> RouteDeclaration | None:
        """Return a named declaration without providing reverse routing."""

        return self._named.get(name)

    def match(self, method: str | HTTPMethod, path: str) -> RouteMatch:
        """Match path specificity first, then the explicit HTTP method."""

        normalized_method = (
            method if isinstance(method, HTTPMethod) else HTTPMethod(method)
        )
        values = _parse_request_path(path)
        for group in self._groups:
            if not _shape_matches(group.shape, values):
                continue
            route = group.routes_by_method.get(normalized_method.value)
            if route is None:
                return RouteMatch.method_not_allowed(
                    HTTPMethod(value) for value in group.routes_by_method
                )
            return RouteMatch.matched(route, group.capture(route, values))
        return RouteMatch.not_found()


def compile_router(declarations: Iterable[RouteDeclaration]) -> Router:
    """Validate and atomically compile an immutable Router."""

    routes = tuple(declarations)
    if any(not isinstance(route, RouteDeclaration) for route in routes):
        raise TypeError("router declarations must be RouteDeclaration values")

    named: dict[str, RouteDeclaration] = {}
    grouped: dict[tuple[tuple[str, str], ...], list[RouteDeclaration]] = {}
    for route in routes:
        if route.name is not None:
            if route.name in named:
                raise _routing_error(
                    "routing.duplicate_name",
                    "A route name is registered more than once.",
                    safe_details={"name": route.name},
                )
            named[route.name] = route
        grouped.setdefault(_shape(route._segments), []).append(route)

    compiled_groups: list[_RouteGroup] = []
    for shape, same_shape in grouped.items():
        routes_by_method: dict[str, RouteDeclaration] = {}
        for route in same_shape:
            for method in route.methods:
                existing = routes_by_method.get(method.value)
                if existing is not None:
                    code = (
                        "routing.method_conflict"
                        if existing.path_template == route.path_template
                        else "routing.ambiguous_template"
                    )
                    raise _routing_error(
                        code,
                        "Route declarations overlap for the same path and method.",
                        safe_details={
                            "method": method.value,
                            "first": existing.path_template,
                            "second": route.path_template,
                        },
                    )
                routes_by_method[method.value] = route
        specificity = tuple(1 if kind == "static" else 0 for kind, _ in shape)
        compiled_groups.append(
            _RouteGroup(shape, specificity, MappingProxyType(routes_by_method))
        )

    compiled_groups.sort(key=lambda group: group.specificity, reverse=True)
    return Router(routes, tuple(compiled_groups), named)


def _normalize_methods(methods: Iterable[str | HTTPMethod]) -> tuple[HTTPMethod, ...]:
    normalized: dict[str, HTTPMethod] = {}
    for raw_method in methods:
        if isinstance(raw_method, HTTPMethod):
            method = raw_method
        elif isinstance(raw_method, str):
            try:
                method = HTTPMethod(raw_method)
            except ProtocolError as exc:
                raise _routing_error(
                    "routing.invalid_method",
                    "A route method is invalid.",
                    cause=exc,
                ) from exc
        else:
            raise TypeError("route methods must be strings or HTTPMethod values")
        if method.value in normalized:
            raise _routing_error(
                "routing.duplicate_method",
                "A route method is declared more than once.",
                safe_details={"method": method.value},
            )
        normalized[method.value] = method
    if not normalized:
        raise _routing_error(
            "routing.methods_required",
            "A route must declare at least one HTTP method.",
        )
    return tuple(normalized[value] for value in sorted(normalized))


def _parse_template(template: str) -> tuple[_Segment, ...]:
    if not isinstance(template, str):
        raise TypeError("route template must be a string")
    if template == "/":
        return ()
    if (
        not template.startswith("/")
        or template.endswith("/")
        or "//" in template
        or "?" in template
        or "#" in template
        or "\x00" in template
    ):
        raise _routing_error(
            "routing.invalid_template",
            "A route template is invalid.",
            safe_details={"template": template},
        )
    try:
        template.encode("ascii", "strict")
    except UnicodeEncodeError as exc:
        raise _routing_error(
            "routing.invalid_template",
            "A route template must be ASCII in P1.",
            safe_details={"template": template},
            cause=exc,
        ) from exc

    parameters: set[str] = set()
    segments: list[_Segment] = []
    for raw_segment in template[1:].split("/"):
        if raw_segment.startswith("{") or raw_segment.endswith("}"):
            if not (raw_segment.startswith("{") and raw_segment.endswith("}")):
                raise _routing_error(
                    "routing.invalid_template",
                    "A route parameter must occupy a complete segment.",
                    safe_details={"template": template},
                )
            parameter = raw_segment[1:-1]
            if _PARAMETER.fullmatch(parameter) is None:
                raise _routing_error(
                    "routing.invalid_parameter",
                    "A route parameter name is invalid.",
                    safe_details={"parameter": parameter},
                )
            if parameter in parameters:
                raise _routing_error(
                    "routing.duplicate_parameter",
                    "A route parameter name is duplicated.",
                    safe_details={"parameter": parameter},
                )
            parameters.add(parameter)
            segments.append(_Segment(parameter=parameter))
        else:
            if "{" in raw_segment or "}" in raw_segment:
                raise _routing_error(
                    "routing.invalid_template",
                    "A route parameter must occupy a complete segment.",
                    safe_details={"template": template},
                )
            segments.append(_Segment(literal=raw_segment))
    return tuple(segments)


def _parse_request_path(path: str) -> tuple[str, ...]:
    if not isinstance(path, str):
        raise TypeError("request path must be a string")
    if not path.startswith("/") or "?" in path or "#" in path or "\x00" in path:
        raise _routing_error(
            "routing.invalid_path",
            "The request path is invalid for routing.",
            fatal_scope=FatalScope.REQUEST,
        )
    try:
        path.encode("ascii", "strict")
    except UnicodeEncodeError as exc:
        raise _routing_error(
            "routing.invalid_path",
            "The request path must be ASCII in P1.",
            fatal_scope=FatalScope.REQUEST,
            cause=exc,
        ) from exc
    if path == "/":
        return ()
    return tuple(path[1:].split("/"))


def _shape(segments: tuple[_Segment, ...]) -> tuple[tuple[str, str], ...]:
    return tuple(
        ("static", segment.literal)
        if segment.literal is not None
        else ("parameter", "")
        for segment in segments
    )


def _shape_matches(shape: tuple[tuple[str, str], ...], values: tuple[str, ...]) -> bool:
    if len(shape) != len(values):
        return False
    return all(
        kind == "parameter" or literal == value
        for (kind, literal), value in zip(shape, values, strict=True)
    )


def _routing_error(
    code: str,
    message: str,
    *,
    safe_details: Mapping[str, object] | None = None,
    fatal_scope: FatalScope = FatalScope.WORKER,
    cause: Exception | None = None,
) -> RoutingError:
    return RoutingError(
        code,
        message,
        fatal_scope=fatal_scope,
        safe_details=safe_details,
        cause=cause,
    )


__all__ = (
    "Handler",
    "RouteDeclaration",
    "RouteMatch",
    "RouteMatchKind",
    "Router",
    "compile_router",
)
