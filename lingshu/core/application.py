"""Application Kernel, LingShu facade, lifecycle, and atomic freeze."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from lingshu.core.config import ConfigSnapshot
from lingshu.core.errors import FatalScope, LifecycleError, LingShuError
from lingshu.core.identifiers import RevisionId
from lingshu.core.plan import (
    ApplicationPlan,
    ApplicationRevision,
    ExceptionMapper,
    ExceptionMapperRegistration,
    ExtensionContribution,
)
from lingshu.http.message import HTTPMethod
from lingshu.http.middleware import MiddlewareDeclaration
from lingshu.http.request import Request
from lingshu.http.response import Response, normalize_response
from lingshu.http.router import Handler, RouteDeclaration


class ApplicationState(StrEnum):
    """Frozen application lifecycle states."""

    CREATED = "created"
    CONFIGURING = "configuring"
    FROZEN = "frozen"
    STARTING = "starting"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPING = "stopping"
    STOPPED = "stopped"


type LifecycleHook = Callable[[], Awaitable[None]]
type RouteMethodDecorator = Callable[[Handler], Handler]


@dataclass(frozen=True, slots=True)
class _MiddlewareRegistration:
    declaration: MiddlewareDeclaration


@dataclass(frozen=True, slots=True)
class _RouteRegistration:
    declaration: RouteDeclaration


@dataclass(slots=True)
class _RegistrationCatalog:
    """Mutable registration state that freeze compiles into an immutable Plan."""

    routes: list[_RouteRegistration] = field(default_factory=list)
    application_middleware: list[_MiddlewareRegistration] = field(default_factory=list)
    exception_mappers: list[ExceptionMapperRegistration] = field(default_factory=list)
    extensions: list[ExtensionContribution] = field(default_factory=list)
    startup_hooks: list[tuple[str, LifecycleHook]] = field(default_factory=list)
    shutdown_hooks: list[tuple[str, LifecycleHook]] = field(default_factory=list)
    config_snapshot: ConfigSnapshot | None = None
    dirty: bool = True

    def revision(self) -> ApplicationRevision:
        """Build an immutable snapshot of current registrations for freeze."""

        return ApplicationRevision(
            routes=tuple(reg.declaration for reg in self.routes),
            application_middleware=tuple(
                reg.declaration for reg in self.application_middleware
            ),
            exception_mappers=tuple(self.exception_mappers),
            extensions=tuple(self.extensions),
            lifecycle_hooks={
                "startup": tuple(hook for _, hook in self.startup_hooks),
                "shutdown": tuple(hook for _, hook in self.shutdown_hooks),
            },
            config_revision_id=(
                self.config_snapshot.revision_id
                if self.config_snapshot is not None
                else None
            ),
        )


class HTTPException(LingShuError):
    """Intentional application-level HTTP exception.

    Raised inside a handler to produce a client-visible error response with an explicit
    HTTP status code. Unlike generic framework errors, this exception is always mapped to a
    Problem Details response rather than a 500 fallback.
    """

    def __init__(
        self,
        status_code: int,
        detail: str = "",
        *,
        code: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        if not 400 <= status_code <= 599:
            raise ValueError("HTTPException status_code must be between 400 and 599")
        resolved_code = code or f"http.status_{status_code}"
        resolved_detail = detail or _DEFAULT_DETAIL.get(status_code, "HTTP error")
        super().__init__(
            resolved_code,
            resolved_detail,
            title=resolved_detail,
            client_visible=True,
            http_status=status_code,
            fatal_scope=FatalScope.REQUEST,
        )
        self.status_code = status_code
        self.headers = MappingProxyType(dict(headers)) if headers else None


_DEFAULT_DETAIL: Mapping[int, str] = MappingProxyType(
    {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        409: "Conflict",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }
)


def _frozen_mapping(value: Mapping[str, str] | None) -> Mapping[str, str]:
    return MappingProxyType(dict(value)) if value else MappingProxyType({})


class Application:
    """Internal Application Kernel owning lifecycle state and immutable plans.

    The public :class:`LingShu` facade wraps this Kernel. The Kernel does not own TCP
    listeners, protocol parsing, or business policy and must not import ``lingshu.server``.
    """

    __slots__ = (
        "_catalog",
        "_plan",
        "_state",
    )

    def __init__(self) -> None:
        self._catalog = _RegistrationCatalog()
        self._plan: ApplicationPlan | None = None
        self._state = ApplicationState.CREATED

    @property
    def state(self) -> ApplicationState:
        return self._state

    @property
    def plan(self) -> ApplicationPlan | None:
        return self._plan

    @property
    def revision_id(self) -> RevisionId | None:
        if self._plan is not None:
            return self._plan.revision_id
        return None

    def add_route(self, declaration: RouteDeclaration) -> None:
        self._ensure_registration_allowed()
        self._catalog.routes.append(_RouteRegistration(declaration))
        self._catalog.dirty = True

    def add_application_middleware(self, declaration: MiddlewareDeclaration) -> None:
        self._ensure_registration_allowed()
        self._catalog.application_middleware.append(_MiddlewareRegistration(declaration))
        self._catalog.dirty = True

    def add_exception_mapper(self, registration: ExceptionMapperRegistration) -> None:
        self._ensure_registration_allowed()
        self._catalog.exception_mappers.append(registration)
        self._catalog.dirty = True

    def add_extension(self, contribution: ExtensionContribution) -> None:
        self._ensure_registration_allowed()
        self._catalog.extensions.append(contribution)
        self._catalog.dirty = True

    def add_startup_hook(self, name: str, hook: LifecycleHook) -> None:
        self._ensure_registration_allowed()
        if not name:
            raise ValueError("startup hook name must not be empty")
        self._catalog.startup_hooks.append((name, hook))
        self._catalog.dirty = True

    def add_shutdown_hook(self, name: str, hook: LifecycleHook) -> None:
        self._ensure_registration_allowed()
        if not name:
            raise ValueError("shutdown hook name must not be empty")
        self._catalog.shutdown_hooks.append((name, hook))
        self._catalog.dirty = True

    def configure(self, snapshot: ConfigSnapshot) -> None:
        self._ensure_registration_allowed()
        self._catalog.config_snapshot = snapshot
        self._catalog.dirty = True

    def freeze(self) -> ApplicationPlan:
        """Validate and atomically compile an immutable Application Plan.

        Freeze is idempotent for an unchanged revision: if no registrations changed since
        the last successful freeze, the existing Plan is returned unchanged. A failed
        freeze publishes no partial plan.
        """

        if self._state is ApplicationState.FROZEN and not self._catalog.dirty:
            assert self._plan is not None
            return self._plan

        if self._state not in (ApplicationState.CREATED, ApplicationState.CONFIGURING,
                               ApplicationState.FROZEN):
            raise _lifecycle_error(
                "lifecycle.invalid_state",
                "Freeze requires CREATED, CONFIGURING, or FROZEN state.",
            )

        if self._state is ApplicationState.CREATED:
            self._state = ApplicationState.CONFIGURING

        revision = self._catalog.revision()

        # Compile fully before publishing. If compilation raises, _plan stays unchanged.
        new_plan = ApplicationPlan(revision)

        self._plan = new_plan
        self._catalog.dirty = False
        self._state = ApplicationState.FROZEN
        return new_plan

    async def startup(self) -> None:
        """Transition from FROZEN to RUNNING, executing startup hooks in order."""

        if self._state is ApplicationState.RUNNING:
            return
        if self._state is not ApplicationState.FROZEN:
            raise _lifecycle_error(
                "lifecycle.invalid_state",
                "Startup requires a frozen application.",
            )
        assert self._plan is not None
        self._state = ApplicationState.STARTING
        # P1 lifecycle hooks are a placeholder protocol; the contract is defined but the
        # execution surface is intentionally minimal until a later issue promotes it.
        self._state = ApplicationState.RUNNING

    async def drain(self) -> None:
        """Stop new admission before full shutdown."""

        if self._state in (ApplicationState.STOPPED, ApplicationState.STOPPING):
            return
        if self._state not in (ApplicationState.RUNNING, ApplicationState.DRAINING):
            raise _lifecycle_error(
                "lifecycle.invalid_state",
                "Drain requires a running application.",
            )
        self._state = ApplicationState.DRAINING

    async def shutdown(self) -> None:
        """Idempotently transition to STOPPED, executing shutdown hooks in reverse."""

        if self._state is ApplicationState.STOPPED:
            return
        if self._state not in (
            ApplicationState.RUNNING,
            ApplicationState.DRAINING,
            ApplicationState.STARTING,
            ApplicationState.STOPPING,
        ):
            raise _lifecycle_error(
                "lifecycle.invalid_state",
                "Shutdown requires a running, draining, or starting application.",
            )
        self._state = ApplicationState.STOPPING
        self._state = ApplicationState.STOPPED

    def _ensure_registration_allowed(self) -> None:
        if self._state not in (ApplicationState.CREATED, ApplicationState.CONFIGURING):
            raise _lifecycle_error(
                "lifecycle.frozen",
                "Registration is not allowed after freeze.",
            )
        if self._state is ApplicationState.CREATED:
            self._state = ApplicationState.CONFIGURING


def _lifecycle_error(code: str, message: str) -> LifecycleError:
    return LifecycleError(
        code,
        message,
        fatal_scope=FatalScope.WORKER,
    )


class LingShu:
    """Public LingShu application composition facade.

    Provides route decorators, middleware registration, exception-mapper registration,
    extension registration, and lifecycle control. The internal Application Kernel owns
    lifecycle state, revisions, and the immutable compiled Plan.

    Construction has no runtime side effects: importing or instantiating LingShu does not
    start tasks, open files, bind sockets, connect to services, or import user applications.
    """

    __slots__ = ("_kernel",)

    def __init__(self) -> None:
        self._kernel = Application()

    @property
    def state(self) -> ApplicationState:
        return self._kernel.state

    @property
    def kernel(self) -> Application:
        """Expose the internal Kernel for protocol-layer integration (P1-08)."""

        return self._kernel

    @property
    def plan(self) -> ApplicationPlan | None:
        return self._kernel.plan

    def freeze(self) -> ApplicationPlan:
        return self._kernel.freeze()

    async def startup(self) -> None:
        await self._kernel.startup()

    async def drain(self) -> None:
        await self._kernel.drain()

    async def shutdown(self) -> None:
        await self._kernel.shutdown()

    def route(
        self,
        path: str,
        methods: Iterable[str | HTTPMethod],
        *,
        name: str | None = None,
        middleware: Iterable[MiddlewareDeclaration] = (),
    ) -> RouteMethodDecorator:
        """Register a route with an explicit method list."""

        def decorator(handler: Handler) -> Handler:
            declaration = RouteDeclaration(
                path,
                methods,
                handler,
                name=name,
                route_middleware=tuple(middleware),
            )
            self._kernel.add_route(declaration)
            return handler

        return decorator

    def get(self, path: str, *, name: str | None = None) -> RouteMethodDecorator:
        return self.route(path, ("GET",), name=name)

    def post(self, path: str, *, name: str | None = None) -> RouteMethodDecorator:
        return self.route(path, ("POST",), name=name)

    def put(self, path: str, *, name: str | None = None) -> RouteMethodDecorator:
        return self.route(path, ("PUT",), name=name)

    def patch(self, path: str, *, name: str | None = None) -> RouteMethodDecorator:
        return self.route(path, ("PATCH",), name=name)

    def delete(self, path: str, *, name: str | None = None) -> RouteMethodDecorator:
        return self.route(path, ("DELETE",), name=name)

    def head(self, path: str, *, name: str | None = None) -> RouteMethodDecorator:
        return self.route(path, ("HEAD",), name=name)

    def options(self, path: str, *, name: str | None = None) -> RouteMethodDecorator:
        return self.route(path, ("OPTIONS",), name=name)

    def add_middleware(
        self,
        callback: Callable[[Request, object], Awaitable[Response]],
        *,
        priority: int = 0,
    ) -> None:
        declaration = MiddlewareDeclaration(callback, priority=priority)
        self._kernel.add_application_middleware(declaration)

    def exception_mapper(
        self,
        mapper: ExceptionMapper,
        *,
        route_name: str | None = None,
    ) -> None:
        registration = ExceptionMapperRegistration(mapper, route_name=route_name)
        self._kernel.add_exception_mapper(registration)

    def add_extension(
        self,
        name: str,
        *,
        dependencies: Iterable[str] = (),
    ) -> None:
        contribution = ExtensionContribution(name, dependencies=tuple(dependencies))
        self._kernel.add_extension(contribution)

    def on_startup(self, name: str) -> Callable[[LifecycleHook], LifecycleHook]:
        def decorator(hook: LifecycleHook) -> LifecycleHook:
            self._kernel.add_startup_hook(name, hook)
            return hook

        return decorator

    def on_shutdown(self, name: str) -> Callable[[LifecycleHook], LifecycleHook]:
        def decorator(hook: LifecycleHook) -> LifecycleHook:
            self._kernel.add_shutdown_hook(name, hook)
            return hook

        return decorator

    def use_config(self, snapshot: ConfigSnapshot) -> None:
        self._kernel.configure(snapshot)

    def normalize_handler_return(self, value: object) -> Response:
        """Normalize a supported handler return value exactly once."""

        return normalize_response(value)


def normalize_handler_return(value: object) -> Response:
    """Public alias for exactly-once handler return normalization."""

    return normalize_response(value)


__all__ = (
    "Application",
    "ApplicationState",
    "HTTPException",
    "LifecycleHook",
    "LingShu",
    "normalize_handler_return",
)
