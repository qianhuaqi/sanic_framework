"""Immutable compiled Application Plan, Mapper resolution, and stable RevisionId."""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from lingshu.core.errors import (
    ConfigurationError,
    FatalScope,
    HandlerContractError,
    LifecycleError,
    RoutingError,
)
from lingshu.core.identifiers import RevisionId
from lingshu.http.middleware import (
    MiddlewareDeclaration,
    MiddlewarePlan,
    MiddlewareScope,
    compile_middleware,
)
from lingshu.http.response import Response
from lingshu.http.router import RouteDeclaration as _RouteDeclaration
from lingshu.http.router import Router, compile_router

_SYNC_RESPONSE = type(None)  # sentinel for sync mapper detection


class MapperScope(StrEnum):
    """Compilation scope for exception mappers."""

    ROUTE = "route"
    APPLICATION = "application"


type SyncExceptionMapper = Callable[[Exception], Response]
type AsyncExceptionMapper = Callable[[Exception], Awaitable[Response]]
type ExceptionMapper = SyncExceptionMapper | AsyncExceptionMapper


@dataclass(frozen=True, slots=True)
class ExceptionMapperRegistration:
    """Immutable registration-time exception-mapper declaration.

    Mappers return :class:`Response`, not :class:`LingShuError`.
    """

    exception_type: type[Exception]
    mapper: ExceptionMapper
    route_name: str | None = None
    registration_sequence: int = 0

    def __post_init__(self) -> None:
        if not (
            isinstance(self.exception_type, type)
            and issubclass(self.exception_type, Exception)
        ):
            raise TypeError("exception_type must be a subclass of Exception")
        if not callable(self.mapper):
            raise TypeError("exception mapper must be callable")
        if self.route_name is not None and not self.route_name:
            raise ValueError("route_name must not be empty when provided")

    @property
    def scope(self) -> MapperScope:
        return MapperScope.ROUTE if self.route_name is not None else MapperScope.APPLICATION

    @property
    def is_async(self) -> bool:
        if inspect.iscoroutinefunction(self.mapper):
            return True
        return inspect.iscoroutinefunction(type(self.mapper).__call__)

    def stable_identity(self) -> tuple[str, ...]:
        """Return a deterministic, hashable identity for RevisionId material."""

        module = getattr(self.exception_type, "__module__", "<unknown>")
        qualname = getattr(self.exception_type, "__qualname__", "<unknown>")
        mapper_module = getattr(self.mapper, "__module__", "<unknown>")
        mapper_qualname = getattr(self.mapper, "__qualname__", "<unknown>")
        return (
            "mapper",
            self.route_name or "",
            f"{module}.{qualname}",
            f"{mapper_module}.{mapper_qualname}",
            str(self.registration_sequence),
        )


@dataclass(frozen=True, slots=True)
class ExtensionContribution:
    """Immutable registered extension contribution with lifecycle hooks."""

    name: str
    dependencies: tuple[str, ...] = ()
    startup_hook: Callable[[], Awaitable[None]] | None = None
    shutdown_hook: Callable[[], Awaitable[None]] | None = None

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

        if self.startup_hook is not None and not _is_async_callable(self.startup_hook):
            raise TypeError("extension startup_hook must be an async callable")
        if self.shutdown_hook is not None and not _is_async_callable(self.shutdown_hook):
            raise TypeError("extension shutdown_hook must be an async callable")

    def stable_identity(self) -> tuple[str, ...]:
        startup_id = _callable_identity(self.startup_hook) if self.startup_hook else ""
        shutdown_id = _callable_identity(self.shutdown_hook) if self.shutdown_hook else ""
        return (
            "extension",
            self.name,
            ",".join(self.dependencies),
            startup_id,
            shutdown_id,
        )


@dataclass(frozen=True, slots=True)
class LifecycleHookRegistration:
    """Immutable lifecycle hook registration with stable identity."""

    name: str
    hook: Callable[[], Awaitable[None]]
    registration_sequence: int = 0

    def stable_identity(self) -> tuple[str, ...]:
        return ("hook", self.name, _callable_identity(self.hook), str(self.registration_sequence))


@dataclass(frozen=True, slots=True)
class ApplicationRevision:
    """Validated registration catalog snapshot that freeze compiles into a Plan."""

    routes: tuple[_RouteDeclaration, ...]
    application_middleware: tuple[MiddlewareDeclaration, ...]
    exception_mappers: tuple[ExceptionMapperRegistration, ...]
    extensions: tuple[ExtensionContribution, ...]
    startup_hooks: tuple[LifecycleHookRegistration, ...]
    shutdown_hooks: tuple[LifecycleHookRegistration, ...]
    config_revision_id: RevisionId | None

    def canonical_bytes(self) -> bytes:
        """Return deterministic canonical bytes for RevisionId hashing.

        Only stable, explicit declaration material is used — no object addresses,
        repr() of callables, unordered sets, or secret plaintext.
        """

        material: list[tuple[str, ...]] = []

        for route in self.routes:
            material.append(self._route_material(route))

        for index, decl in enumerate(self.application_middleware):
            material.append(self._middleware_material(decl, index))

        for mapper in self.exception_mappers:
            material.append(mapper.stable_identity())

        for extension in self.extensions:
            material.append(extension.stable_identity())

        for hook in self.startup_hooks:
            material.append(("startup", *hook.stable_identity()))
        for hook in self.shutdown_hooks:
            material.append(("shutdown", *hook.stable_identity()))

        material.append(
            ("config", str(self.config_revision_id) if self.config_revision_id else "")
        )

        # Deterministic sort ensures order independence of the hash input is NOT desired —
        # registration order is semantically meaningful. We preserve list order.
        document = json.dumps(
            [list(item) for item in material],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=False,
        )
        return document.encode("utf-8")

    def revision_id(self) -> RevisionId:
        """Return the deterministic SHA-256 identity of this Revision."""

        return RevisionId.from_canonical_bytes(self.canonical_bytes())

    def _route_material(self, route: _RouteDeclaration) -> tuple[str, ...]:
        middleware_ids = ",".join(
            _callable_identity(decl.callback) for decl in route.route_middleware
        )
        return (
            "route",
            route.path_template,
            ",".join(method.value for method in route.methods),
            route.name or "",
            middleware_ids,
        )

    def _middleware_material(self, decl: MiddlewareDeclaration, index: int) -> tuple[str, ...]:
        return (
            "app_middleware",
            _callable_identity(decl.callback),
            str(decl.priority),
            str(index),
        )


@dataclass(frozen=True, slots=True)
class ExtensionLifecyclePlan:
    """Compiled extension startup/shutdown order with hooks."""

    startup_order: tuple[str, ...]
    shutdown_order: tuple[str, ...]
    extensions_by_name: Mapping[str, ExtensionContribution] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, init=False)
class ApplicationPlan:
    """Immutable atomically-published compiled Application Plan."""

    revision_id: RevisionId
    router: Router
    application_middleware: MiddlewarePlan
    route_middleware: Mapping[str, MiddlewarePlan]
    exception_mappers: tuple[ExceptionMapperRegistration, ...]
    extension_plan: ExtensionLifecyclePlan
    startup_hooks: tuple[LifecycleHookRegistration, ...]
    shutdown_hooks: tuple[LifecycleHookRegistration, ...]
    config_revision_id: RevisionId | None

    def __init__(self, revision: ApplicationRevision) -> None:
        # All validation happens before any attribute is set. If any step raises,
        # the Plan object is never published (no __setattr__ calls were made).
        router = _compile_router_safe(revision.routes)
        app_middleware = _compile_middleware_safe(
            MiddlewareScope.APPLICATION,
            revision.application_middleware,
        )
        route_middleware = _compile_all_route_middleware(revision.routes)

        _validate_mappers(revision.exception_mappers, router)
        extension_plan = _resolve_extension_order(revision.extensions)

        _validate_handler_signatures(revision.routes)
        _validate_callable_stability(revision)

        object.__setattr__(self, "revision_id", revision.revision_id())
        object.__setattr__(self, "router", router)
        object.__setattr__(self, "application_middleware", app_middleware)
        object.__setattr__(self, "route_middleware", MappingProxyType(route_middleware))
        object.__setattr__(self, "exception_mappers", revision.exception_mappers)
        object.__setattr__(self, "extension_plan", extension_plan)
        object.__setattr__(self, "startup_hooks", revision.startup_hooks)
        object.__setattr__(self, "shutdown_hooks", revision.shutdown_hooks)
        object.__setattr__(self, "config_revision_id", revision.config_revision_id)


def _is_async_callable(callback: object) -> bool:
    if inspect.iscoroutinefunction(callback):
        return True
    if not callable(callback):
        return False
    return inspect.iscoroutinefunction(type(callback).__call__)


def _callable_identity(func: Callable[..., object]) -> str:
    """Return a stable module.qualname identity for a callable.

    If the callable cannot provide a stable identity, freeze must reject it.
    """

    module = getattr(func, "__module__", None)
    qualname = getattr(func, "__qualname__", None)
    if module is None or qualname is None:
        raise ConfigurationError(
            "freeze.unstable_callable",
            "A registered callable does not provide a stable module/qualname identity.",
            fatal_scope=FatalScope.WORKER,
        )
    return f"{module}.{qualname}"


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


def _compile_all_route_middleware(
    routes: Iterable[_RouteDeclaration],
) -> dict[str, MiddlewarePlan]:
    """Compile a MiddlewarePlan for each named route at freeze time."""

    plans: dict[str, MiddlewarePlan] = {}
    for route in routes:
        if route.name is None:
            continue
        plans[route.name] = _compile_middleware_safe(
            MiddlewareScope.ROUTE,
            route.route_middleware,
        )
    return plans


def _validate_mappers(
    mappers: tuple[ExceptionMapperRegistration, ...],
    router: Router,
) -> None:
    """Validate mapper targets and detect ambiguity at freeze."""

    route_names = {route.name for route in router.routes if route.name is not None}

    # Validate route references and check ambiguity per scope+type.
    route_by_type: dict[tuple[str, type[Exception]], ExceptionMapperRegistration] = {}
    app_by_type: dict[type[Exception], ExceptionMapperRegistration] = {}

    for mapper in mappers:
        if mapper.route_name is not None:
            if mapper.route_name not in route_names:
                raise _freeze_error(
                    "freeze.mapper_unknown_route",
                    "An exception mapper references an unknown route.",
                    safe_details={"route_name": mapper.route_name},
                )
            key = (mapper.route_name, mapper.exception_type)
            if key in route_by_type:
                raise _freeze_error(
                    "freeze.mapper_ambiguous",
                    "Duplicate exception mapper for the same route and exception type.",
                    safe_details={
                        "route_name": mapper.route_name,
                        "exception_type": mapper.exception_type.__name__,
                    },
                )
            route_by_type[key] = mapper
        else:
            if mapper.exception_type in app_by_type:
                raise _freeze_error(
                    "freeze.mapper_ambiguous",
                    "Duplicate application-scoped exception mapper for the same exception type.",
                    safe_details={"exception_type": mapper.exception_type.__name__},
                )
            app_by_type[mapper.exception_type] = mapper


def _resolve_extension_order(
    extensions: tuple[ExtensionContribution, ...],
) -> ExtensionLifecyclePlan:
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

    return ExtensionLifecyclePlan(
        tuple(startup),
        tuple(reversed(startup)),
        MappingProxyType(by_name),
    )


def _validate_handler_signatures(routes: tuple[_RouteDeclaration, ...]) -> None:
    """Strictly validate that every handler is async def with exactly one positional param."""

    for route in routes:
        handler = route.handler
        if not inspect.iscoroutinefunction(handler):
            raise HandlerContractError(
                "handler.async_required",
                "Route handlers must be asynchronous in P1.",
                fatal_scope=FatalScope.WORKER,
                safe_details={"path": route.path_template},
            )
        signature = inspect.signature(handler)
        params = list(signature.parameters.values())

        # Reject *args and **kwargs entirely.
        for param in params:
            if param.kind is inspect.Parameter.VAR_POSITIONAL:
                raise HandlerContractError(
                    "handler.signature",
                    "Route handlers must not accept *args in P1.",
                    fatal_scope=FatalScope.WORKER,
                    safe_details={"path": route.path_template},
                )
            if param.kind is inspect.Parameter.VAR_KEYWORD:
                raise HandlerContractError(
                    "handler.signature",
                    "Route handlers must not accept **kwargs in P1.",
                    fatal_scope=FatalScope.WORKER,
                    safe_details={"path": route.path_template},
                )

        # Exactly one positional parameter.
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

        # Reject required keyword-only parameters.
        keyword_only = [
            param
            for param in params
            if param.kind is inspect.Parameter.KEYWORD_ONLY
            and param.default is inspect.Parameter.empty
        ]
        if keyword_only:
            raise HandlerContractError(
                "handler.signature",
                "Route handlers must not have required keyword-only parameters in P1.",
                fatal_scope=FatalScope.WORKER,
                safe_details={"path": route.path_template},
            )


def _validate_callable_stability(revision: ApplicationRevision) -> None:
    """Ensure all registered callables provide stable module/qualname identities."""

    for route in revision.routes:
        _callable_identity(route.handler)

    for mapper in revision.exception_mappers:
        _callable_identity(mapper.mapper)

    for hook in revision.startup_hooks:
        _callable_identity(hook.hook)
    for hook in revision.shutdown_hooks:
        _callable_identity(hook.hook)

    for ext in revision.extensions:
        if ext.startup_hook is not None:
            _callable_identity(ext.startup_hook)
        if ext.shutdown_hook is not None:
            _callable_identity(ext.shutdown_hook)


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


# Required for Mapping type annotation at runtime.
__all__ = (
    "ApplicationPlan",
    "ApplicationRevision",
    "AsyncExceptionMapper",
    "ExceptionMapper",
    "ExceptionMapperRegistration",
    "ExtensionContribution",
    "ExtensionLifecyclePlan",
    "LifecycleHookRegistration",
    "MapperScope",
    "SyncExceptionMapper",
)
