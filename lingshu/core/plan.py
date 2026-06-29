"""Immutable compiled Application Plan and exception-mapper resolution."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass

from lingshu.core.errors import (
    ConfigurationError,
    FatalScope,
    HandlerContractError,
    LifecycleError,
    LingShuError,
    RoutingError,
)
from lingshu.core.identifiers import RevisionId
from lingshu.http.middleware import (
    MiddlewareDeclaration,
    MiddlewarePlan,
    MiddlewareScope,
    compile_middleware,
)
from lingshu.http.router import RouteDeclaration as _RouteDeclaration
from lingshu.http.router import Router, compile_router

type ExceptionMapper = Callable[[Exception], LingShuError]


@dataclass(frozen=True, slots=True)
class ExceptionMapperRegistration:
    """Immutable registration-time exception-mapper declaration."""

    mapper: ExceptionMapper
    route_name: str | None = None

    def __post_init__(self) -> None:
        if not callable(self.mapper):
            raise TypeError("exception mapper must be callable")
        if self.route_name is not None and not self.route_name:
            raise ValueError("route_name must not be empty when provided")


@dataclass(frozen=True, slots=True)
class ExtensionContribution:
    """Immutable placeholder for a registered extension contribution."""

    name: str
    dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("extension name must not be empty")
        frozen: list[str] = []
        for dependency in self.dependencies:
            if not isinstance(dependency, str) or not dependency:
                raise TypeError("extension dependencies must be non-empty strings")
            if dependency in frozen:
                raise ValueError(f"duplicate extension dependency: {dependency}")
            frozen.append(dependency)
        object.__setattr__(self, "dependencies", tuple(frozen))


@dataclass(frozen=True, slots=True)
class ApplicationRevision:
    """Validated mutable registration catalog that freeze compiles into a Plan."""

    routes: tuple[_RouteDeclaration, ...]
    application_middleware: tuple[MiddlewareDeclaration, ...]
    exception_mappers: tuple[ExceptionMapperRegistration, ...]
    extensions: tuple[ExtensionContribution, ...]
    lifecycle_hooks: Mapping[str, tuple[Callable[[], Awaitable[None]], ...]]
    config_revision_id: RevisionId | None

    def canonical_bytes(self) -> bytes:
        """Return deterministic canonical bytes for RevisionId hashing."""

        document = {
            "routes": [
                {
                    "path": route.path_template,
                    "methods": tuple(method.value for method in route.methods),
                    "name": route.name,
                }
                for route in self.routes
            ],
            "application_middleware": len(self.application_middleware),
            "exception_mappers": tuple(
                {"route_name": mapper.route_name} for mapper in self.exception_mappers
            ),
            "extensions": tuple(
                {"name": ext.name, "dependencies": ext.dependencies}
                for ext in self.extensions
            ),
            "lifecycle_hooks": {
                key: len(hooks) for key, hooks in self.lifecycle_hooks.items()
            },
            "config_revision_id": str(self.config_revision_id)
            if self.config_revision_id is not None
            else None,
        }
        return json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    def revision_id(self) -> RevisionId:
        """Return the deterministic SHA-256 identity of this Revision."""

        return RevisionId.from_canonical_bytes(self.canonical_bytes())


@dataclass(frozen=True, slots=True)
class ExtensionStartupPlan:
    """Compiled extension lifecycle order."""

    startup_order: tuple[str, ...]
    shutdown_order: tuple[str, ...]


@dataclass(frozen=True, slots=True, init=False)
class ApplicationPlan:
    """Immutable atomically-published compiled Application Plan."""

    revision_id: RevisionId
    router: Router
    application_middleware: MiddlewarePlan
    exception_mappers: tuple[ExceptionMapperRegistration, ...]
    extension_plan: ExtensionStartupPlan
    config_revision_id: RevisionId | None

    def __init__(self, revision: ApplicationRevision) -> None:
        router = _compile_router_safe(revision.routes)
        app_middleware = _compile_middleware_safe(
            MiddlewareScope.APPLICATION,
            (decl for decl in revision.application_middleware),
        )

        _validate_mappers(revision.exception_mappers, router)
        extension_plan = _resolve_extension_order(revision.extensions)

        _validate_handler_signatures(revision.routes)

        object.__setattr__(self, "revision_id", revision.revision_id())
        object.__setattr__(self, "router", router)
        object.__setattr__(self, "application_middleware", app_middleware)
        object.__setattr__(self, "exception_mappers", revision.exception_mappers)
        object.__setattr__(self, "extension_plan", extension_plan)
        object.__setattr__(self, "config_revision_id", revision.config_revision_id)

    def resolve_exception(self, error: BaseException, route_name: str | None) -> LingShuError:
        """Resolve an exception to a client-safe LingShuError.

        Control-flow exceptions deriving from :class:`BaseException` (including
        :class:`asyncio.CancelledError`) are re-raised unchanged and are never converted to
        an ordinary error response.
        """

        import asyncio

        if isinstance(error, asyncio.CancelledError) or not isinstance(error, Exception):
            raise TypeError(
                "control-flow BaseException values must not be mapped as ordinary errors"
            )

        # Resolution order: most-specific route mapper → app-scoped mapper → fallback.
        for mapper in self.exception_mappers:
            if mapper.route_name is not None and mapper.route_name == route_name:
                return _invoke_mapper(mapper.mapper, error)
        for mapper in self.exception_mappers:
            if mapper.route_name is None:
                return _invoke_mapper(mapper.mapper, error)

        if isinstance(error, LingShuError):
            return error

        return LingShuError(
            "internal.unhandled",
            "An internal error occurred.",
            fatal_scope=FatalScope.REQUEST,
            cause=error,
        )


def _compile_router_safe(routes: Iterable[_RouteDeclaration]) -> Router:
    routes_tuple = tuple(routes)
    try:
        return compile_router(routes_tuple)
    except RoutingError:
        raise
    except Exception as exc:
        raise _freeze_error(
            "freeze.route_compilation_failed",
            "Route compilation failed.",
            cause=exc,
        ) from exc


def _compile_middleware_safe(
    scope: MiddlewareScope,
    declarations: Iterable[MiddlewareDeclaration],
) -> MiddlewarePlan:
    entries = tuple(declarations)
    try:
        return compile_middleware(scope, entries)
    except (HandlerContractError, LifecycleError):
        raise
    except Exception as exc:
        raise _freeze_error(
            "freeze.middleware_compilation_failed",
            "Middleware compilation failed.",
            cause=exc,
        ) from exc


def _validate_mappers(
    mappers: tuple[ExceptionMapperRegistration, ...],
    router: Router,
) -> None:
    route_names = set()
    for route in router.routes:
        if route.name is not None:
            route_names.add(route.name)

    seen_route: dict[str, ExceptionMapperRegistration] = {}
    app_mapper: ExceptionMapperRegistration | None = None
    for mapper in mappers:
        if mapper.route_name is not None:
            if mapper.route_name not in route_names:
                raise _freeze_error(
                    "freeze.mapper_unknown_route",
                    "An exception mapper references an unknown route.",
                    safe_details={"route_name": mapper.route_name},
                )
            if mapper.route_name in seen_route:
                raise _freeze_error(
                    "freeze.mapper_ambiguous",
                    "Multiple exception mappers target the same route.",
                    safe_details={"route_name": mapper.route_name},
                )
            seen_route[mapper.route_name] = mapper
        else:
            if app_mapper is not None:
                raise _freeze_error(
                    "freeze.mapper_ambiguous",
                    "Multiple application-scoped exception mappers are ambiguous.",
                )
            app_mapper = mapper


def _resolve_extension_order(
    extensions: tuple[ExtensionContribution, ...],
) -> ExtensionStartupPlan:
    by_name: dict[str, ExtensionContribution] = {}
    for extension in extensions:
        if extension.name in by_name:
            raise _freeze_error(
                "freeze.duplicate_extension",
                "An extension name is registered more than once.",
                safe_details={"name": extension.name},
            )
        by_name[extension.name] = extension

    startup: list[str] = []
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise _freeze_error(
                "freeze.extension_cycle",
                "Extension dependencies contain a cycle.",
                safe_details={"name": name},
            )
        visiting.add(name)
        extension = by_name[name]
        for dependency in extension.dependencies:
            if dependency not in by_name:
                raise _freeze_error(
                    "freeze.extension_unknown_dependency",
                    "An extension declares an unknown dependency.",
                    safe_details={"name": name, "dependency": dependency},
                )
            visit(dependency)
        visiting.discard(name)
        visited.add(name)
        startup.append(name)

    for name in by_name:
        visit(name)

    return ExtensionStartupPlan(tuple(startup), tuple(reversed(startup)))


def _validate_handler_signatures(routes: tuple[_RouteDeclaration, ...]) -> None:
    import inspect

    for route in routes:
        handler = route.handler
        if not inspect.iscoroutinefunction(handler):
            if callable(handler) and inspect.iscoroutinefunction(type(handler).__call__):
                continue
            raise HandlerContractError(
                "handler.async_required",
                "Route handlers must be asynchronous in P1.",
                fatal_scope=FatalScope.WORKER,
                safe_details={"path": route.path_template},
            )
        signature = inspect.signature(handler)
        params = list(signature.parameters.values())
        positional = [
            param
            for param in params
            if param.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        if len(positional) != 1:
            raise HandlerContractError(
                "handler.signature",
                "Route handlers must accept exactly one positional parameter in P1.",
                fatal_scope=FatalScope.WORKER,
                safe_details={"path": route.path_template},
            )


def _invoke_mapper(mapper: ExceptionMapper, error: Exception) -> LingShuError:
    try:
        result = mapper(error)
    except Exception as mapper_error:
        return LingShuError(
            "internal.mapper_failed",
            "An internal error occurred.",
            fatal_scope=FatalScope.REQUEST,
            cause=mapper_error,
        )
    return result


def _freeze_error(
    code: str,
    message: str,
    *,
    safe_details: Mapping[str, object] | None = None,
    cause: Exception | None = None,
) -> ConfigurationError:
    return ConfigurationError(
        code,
        message,
        fatal_scope=FatalScope.WORKER,
        safe_details=safe_details,
        cause=cause,
    )


__all__ = (
    "ApplicationPlan",
    "ApplicationRevision",
    "ExceptionMapper",
    "ExceptionMapperRegistration",
    "ExtensionContribution",
    "ExtensionStartupPlan",
)
