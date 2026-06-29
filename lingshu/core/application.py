"""Application Kernel, LingShu facade, lifecycle, dispatch, and atomic freeze."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

from lingshu.core.config import ConfigSnapshot
from lingshu.core.errors import FatalScope, LifecycleError
from lingshu.core.identifiers import RevisionId
from lingshu.core.plan import (
    ApplicationPlan,
    ApplicationRevision,
    ExceptionMapperRegistration,
    ExtensionContribution,
    LifecycleHookRegistration,
)
from lingshu.http.message import HTTPMethod
from lingshu.http.middleware import MiddlewareDeclaration, Terminal
from lingshu.http.request import Request
from lingshu.http.response import Response, normalize_response
from lingshu.http.router import Handler, RouteDeclaration, RouteMatchKind


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
class _RouteRegistration:
    declaration: RouteDeclaration
    sequence: int


@dataclass(frozen=True, slots=True)
class _MiddlewareRegistration:
    declaration: MiddlewareDeclaration
    sequence: int


@dataclass(slots=True)
class _RegistrationCatalog:
    """Mutable registration state that freeze compiles into an immutable Plan."""

    routes: list[_RouteRegistration] = field(default_factory=list)
    application_middleware: list[_MiddlewareRegistration] = field(default_factory=list)
    exception_mappers: list[ExceptionMapperRegistration] = field(default_factory=list)
    extensions: list[ExtensionContribution] = field(default_factory=list)
    startup_hooks: list[LifecycleHookRegistration] = field(default_factory=list)
    shutdown_hooks: list[LifecycleHookRegistration] = field(default_factory=list)
    config_snapshot: ConfigSnapshot | None = None
    _sequence: int = 0
    dirty: bool = True

    def _next_sequence(self) -> int:
        seq = self._sequence
        self._sequence += 1
        return seq

    def add_route(self, declaration: RouteDeclaration) -> None:
        self.routes.append(_RouteRegistration(declaration, self._next_sequence()))
        self.dirty = True

    def add_middleware(self, declaration: MiddlewareDeclaration) -> None:
        self.application_middleware.append(
            _MiddlewareRegistration(declaration, self._next_sequence())
        )
        self.dirty = True

    def add_mapper(self, registration: ExceptionMapperRegistration) -> None:
        seq = self._next_sequence()
        # Re-create with sequence assigned.
        fixed = ExceptionMapperRegistration(
            exception_type=registration.exception_type,
            mapper=registration.mapper,
            route_name=registration.route_name,
            registration_sequence=seq,
        )
        self.exception_mappers.append(fixed)
        self.dirty = True

    def add_extension(self, contribution: ExtensionContribution) -> None:
        self.extensions.append(contribution)
        self.dirty = True

    def add_startup_hook(self, name: str, hook: LifecycleHook) -> None:
        seq = self._next_sequence()
        self.startup_hooks.append(LifecycleHookRegistration(name, hook, seq))
        self.dirty = True

    def add_shutdown_hook(self, name: str, hook: LifecycleHook) -> None:
        seq = self._next_sequence()
        self.shutdown_hooks.append(LifecycleHookRegistration(name, hook, seq))
        self.dirty = True

    def revision(self) -> ApplicationRevision:
        """Build an immutable snapshot of current registrations for freeze."""

        return ApplicationRevision(
            routes=tuple(reg.declaration for reg in self.routes),
            application_middleware=tuple(reg.declaration for reg in self.application_middleware),
            exception_mappers=tuple(self.exception_mappers),
            extensions=tuple(self.extensions),
            startup_hooks=tuple(self.startup_hooks),
            shutdown_hooks=tuple(self.shutdown_hooks),
            config_revision_id=(
                self.config_snapshot.revision_id if self.config_snapshot is not None else None
            ),
        )


class Application:
    """Internal Application Kernel owning lifecycle state and immutable plans.

    The Kernel does not own TCP listeners, protocol parsing, or business policy and must
    not import ``lingshu.server``.
    """

    __slots__ = (
        "_catalog",
        "_extensions_started",
        "_plan",
        "_state",
    )

    def __init__(self) -> None:
        self._catalog = _RegistrationCatalog()
        self._plan: ApplicationPlan | None = None
        self._state = ApplicationState.CREATED
        self._extensions_started: list[str] = []

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
        self._catalog.add_route(declaration)

    def add_application_middleware(self, declaration: MiddlewareDeclaration) -> None:
        self._ensure_registration_allowed()
        self._catalog.add_middleware(declaration)

    def add_exception_mapper(self, registration: ExceptionMapperRegistration) -> None:
        self._ensure_registration_allowed()
        self._catalog.add_mapper(registration)

    def add_extension(self, contribution: ExtensionContribution) -> None:
        self._ensure_registration_allowed()
        self._catalog.add_extension(contribution)

    def add_startup_hook(self, name: str, hook: LifecycleHook) -> None:
        self._ensure_registration_allowed()
        if not name:
            raise ValueError("startup hook name must not be empty")
        self._catalog.add_startup_hook(name, hook)

    def add_shutdown_hook(self, name: str, hook: LifecycleHook) -> None:
        self._ensure_registration_allowed()
        if not name:
            raise ValueError("shutdown hook name must not be empty")
        self._catalog.add_shutdown_hook(name, hook)

    def configure(self, snapshot: ConfigSnapshot) -> None:
        self._ensure_registration_allowed()
        self._catalog.config_snapshot = snapshot
        self._catalog.dirty = True

    def freeze(self) -> ApplicationPlan:
        """Validate and atomically compile an immutable Application Plan.

        Freeze is idempotent for an unchanged revision. A failed freeze publishes no
        partial plan and the previous Plan, if any, remains intact.
        """

        if self._state is ApplicationState.FROZEN and not self._catalog.dirty:
            assert self._plan is not None
            return self._plan

        if self._state not in (
            ApplicationState.CREATED,
            ApplicationState.CONFIGURING,
            ApplicationState.FROZEN,
        ):
            raise _lifecycle_error(
                "lifecycle.invalid_state",
                "Freeze requires CREATED, CONFIGURING, or FROZEN state.",
            )

        if self._state is ApplicationState.CREATED:
            self._state = ApplicationState.CONFIGURING

        revision = self._catalog.revision()

        # ApplicationPlan.__init__ does ALL validation. If it raises, _plan stays unchanged.
        new_plan = ApplicationPlan(revision)

        self._plan = new_plan
        self._catalog.dirty = False
        self._state = ApplicationState.FROZEN
        return new_plan

    async def startup(self) -> None:
        """Transition from FROZEN to RUNNING, executing all startup hooks and extensions."""

        if self._state is ApplicationState.RUNNING:
            return
        if self._state is not ApplicationState.FROZEN:
            raise _lifecycle_error(
                "lifecycle.invalid_state",
                "Startup requires a frozen application.",
            )
        assert self._plan is not None

        self._state = ApplicationState.STARTING
        started_extensions: list[str] = []

        try:
            # Execute application startup hooks.
            for hook_reg in self._plan.startup_hooks:
                await hook_reg.hook()

            # Execute extension startup in dependency order.
            ext_plan = self._plan.extension_plan
            for name in ext_plan.startup_order:
                ext = ext_plan.extensions_by_name.get(name)
                if ext is not None and ext.startup_hook is not None:
                    await ext.startup_hook()
                started_extensions.append(name)

        except BaseException:
            # Rollback: shutdown already-started extensions in reverse order.
            for name in reversed(started_extensions):
                ext = ext_plan.extensions_by_name.get(name)
                if ext is not None and ext.shutdown_hook is not None:
                    with suppress(Exception):
                        await ext.shutdown_hook()
            self._state = ApplicationState.FROZEN
            self._extensions_started = []
            raise

        self._extensions_started = started_extensions
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
        """Idempotently transition to STOPPED, executing shutdown in reverse order."""

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

        assert self._plan is not None

        # Shutdown extensions in reverse startup order.
        for name in reversed(self._extensions_started):
            ext = self._plan.extension_plan.extensions_by_name.get(name)
            if ext is not None and ext.shutdown_hook is not None:
                with suppress(Exception):
                    await ext.shutdown_hook()

        # Execute application shutdown hooks in reverse order.
        for hook_reg in reversed(self._plan.shutdown_hooks):
            with suppress(Exception):
                await hook_reg.hook()

        self._extensions_started = []
        self._state = ApplicationState.STOPPED

    async def dispatch(self, method: str, path: str, request: Request) -> Response:
        """Execute the canonical request pipeline for one request.

        This is the internal dispatch used by the protocol layer (P1-08). It does NOT
        own Transport, commit/write, or Runtime Record.

        Pipeline:
        1. application middleware ingress
        2. route match
        3. 404 / 405 / MATCH branching
        4. MATCH: publish immutable route identity and path params
        5. route middleware ingress
        6. invoke async handler
        7. normalize handler return exactly once
        8. route middleware egress
        9. application middleware egress
        10. exception mapping and safe fallback

        BaseException control flow (CancelledError, KeyboardInterrupt, SystemExit, etc.)
        is always re-raised unchanged.
        """

        if self._state is not ApplicationState.RUNNING:
            raise _lifecycle_error(
                "lifecycle.invalid_state",
                "Dispatch requires a running application.",
            )
        assert self._plan is not None
        plan = self._plan

        try:
            return await self._run_pipeline(method, path, request, plan)
        except BaseException as exc:
            # Never convert BaseException control flow into a Response.
            if not isinstance(exc, Exception):
                raise
            return await self._resolve_exception(exc, plan, request)

    async def _run_pipeline(
        self,
        method: str,
        path: str,
        request: Request,
        plan: ApplicationPlan,
    ) -> Response:
        """Execute the full application-middleware → route-match → handler pipeline.

        Route matching happens *inside* the application middleware terminal so that
        application middleware can observe, short-circuit, or handle routing-phase
        outcomes (404, 405) and exceptions.
        """

        async def app_terminal(req: Request) -> Response:
            match = plan.router.match(method, path)

            if match.kind is RouteMatchKind.NOT_FOUND:
                return Response.text("Not Found", status=404)
            if match.kind is RouteMatchKind.METHOD_NOT_ALLOWED:
                allowed = ",".join(
                    m.value for m in sorted(match.allowed_methods, key=lambda m: m.value)
                )
                return Response.text(
                    "Method Not Allowed",
                    status=405,
                    headers=[("allow", allowed)],
                )

            # MATCH: publish route identity and path params.
            assert match.route is not None
            route = match.route
            route_label = route.name or route.path_template
            request.publish_route(route_label, match.path_params)

            # Build the inner terminal: handler → normalize.
            async def handler_terminal(req: Request) -> Response:
                raw = await route.handler(req)
                return normalize_response(raw)

            # Select route middleware plan by stable identity.
            identity = (route.path_template, tuple(m.value for m in route.methods))
            route_plan = plan.route_middleware.get(identity)

            if route_plan is not None and route_plan.declarations:
                return await route_plan.run(req, cast(Terminal, handler_terminal))

            return await handler_terminal(req)

        return await plan.application_middleware.run(request, cast(Terminal, app_terminal))

    async def _resolve_exception(
        self,
        error: Exception,
        plan: ApplicationPlan,
        request: Request,
    ) -> Response:
        """Resolve an exception to a Response via mapper chain or safe fallback."""

        route_name = request.route_name

        # 1. Route-scoped mappers (most-specific exception type via MRO).
        response = await self._try_mappers(
            plan.exception_mappers, error, route_name, route_only=True
        )
        if response is not None:
            return response

        # 2. Application-scoped mappers (most-specific exception type via MRO).
        response = await self._try_mappers(
            plan.exception_mappers, error, route_name, route_only=False
        )
        if response is not None:
            return response

        # 3. Built-in HTTPException mapping.
        from lingshu.http.exceptions import HTTPException

        if isinstance(error, HTTPException):
            resp = Response.text(error.safe_message, status=error.status_code)
            if error.headers:
                for name, value in error.headers.items():
                    resp.set_header(name, value)
            return resp

        # 4. Safe 500 internal error response.
        return Response.text("Internal Server Error", status=500)

    async def _try_mappers(
        self,
        mappers: tuple[ExceptionMapperRegistration, ...],
        error: Exception,
        route_name: str | None,
        *,
        route_only: bool,
    ) -> Response | None:
        """Find the most-specific mapper for the exception type using MRO distance.

        MRO distance 0 is the most specific (exact type match); larger distances are
        less specific ancestors. The mapper with the smallest distance wins. Ties are
        broken by earliest registration sequence for determinism.
        """

        best: ExceptionMapperRegistration | None = None
        best_distance: int | None = None

        for mapper in mappers:
            if route_only:
                if mapper.route_name is None or mapper.route_name != route_name:
                    continue
            else:
                if mapper.route_name is not None:
                    continue

            distance = _mro_distance(error.__class__, mapper.exception_type)
            if distance < 0:
                continue

            if best_distance is None or distance < best_distance:
                best_distance = distance
                best = mapper
            elif distance == best_distance and best is not None:
                if mapper.registration_sequence < best.registration_sequence:
                    best = mapper

        if best is None:
            return None

        return await _invoke_mapper(best.mapper, error)

    def _ensure_registration_allowed(self) -> None:
        if self._state not in (ApplicationState.CREATED, ApplicationState.CONFIGURING):
            raise _lifecycle_error(
                "lifecycle.frozen",
                "Registration is not allowed after freeze.",
            )
        if self._state is ApplicationState.CREATED:
            self._state = ApplicationState.CONFIGURING


def _mro_distance(actual: type[Exception], registered: type[Exception]) -> int:
    """Return the MRO distance from ``actual`` to ``registered``.

    Returns 0 for exact match, 1 for direct parent, etc. Returns -1 if ``registered``
    is not in the MRO of ``actual``.
    """

    for index, cls in enumerate(actual.__mro__):
        if cls is registered:
            return index
    return -1


async def _invoke_mapper(
    mapper: Callable[..., object],
    error: Exception,
) -> Response:
    """Invoke a mapper and validate it returns a Response."""

    try:
        result = mapper(error)
        if inspect.isawaitable(result):
            result = await result
    except Exception:
        return _safe_500()

    if not isinstance(result, Response):
        return _safe_500()
    return result


def _safe_500() -> Response:
    return Response.text("Internal Server Error", status=500)


def _lifecycle_error(code: str, message: str) -> LifecycleError:
    return LifecycleError(
        code,
        message,
        fatal_scope=FatalScope.WORKER,
    )


class LingShu:
    """Public LingShu application composition facade.

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

    async def dispatch(self, method: str, path: str, request: Request) -> Response:
        """Execute the canonical request pipeline for one request."""

        return await self._kernel.dispatch(method, path, request)

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

    def get(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: Iterable[MiddlewareDeclaration] = (),
    ) -> RouteMethodDecorator:
        return self.route(path, ("GET",), name=name, middleware=middleware)

    def post(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: Iterable[MiddlewareDeclaration] = (),
    ) -> RouteMethodDecorator:
        return self.route(path, ("POST",), name=name, middleware=middleware)

    def put(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: Iterable[MiddlewareDeclaration] = (),
    ) -> RouteMethodDecorator:
        return self.route(path, ("PUT",), name=name, middleware=middleware)

    def patch(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: Iterable[MiddlewareDeclaration] = (),
    ) -> RouteMethodDecorator:
        return self.route(path, ("PATCH",), name=name, middleware=middleware)

    def delete(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: Iterable[MiddlewareDeclaration] = (),
    ) -> RouteMethodDecorator:
        return self.route(path, ("DELETE",), name=name, middleware=middleware)

    def head(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: Iterable[MiddlewareDeclaration] = (),
    ) -> RouteMethodDecorator:
        return self.route(path, ("HEAD",), name=name, middleware=middleware)

    def options(
        self,
        path: str,
        *,
        name: str | None = None,
        middleware: Iterable[MiddlewareDeclaration] = (),
    ) -> RouteMethodDecorator:
        return self.route(path, ("OPTIONS",), name=name, middleware=middleware)

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
        exception_type: type[Exception],
        mapper: Callable[..., object],
        *,
        route_name: str | None = None,
    ) -> None:
        registration = ExceptionMapperRegistration(
            exception_type=exception_type,
            mapper=mapper,  # type: ignore[arg-type]
            route_name=route_name,
        )
        self._kernel.add_exception_mapper(registration)

    def add_extension(
        self,
        name: str,
        *,
        dependencies: Iterable[str] = (),
        startup_hook: LifecycleHook | None = None,
        shutdown_hook: LifecycleHook | None = None,
    ) -> None:
        contribution = ExtensionContribution(
            name,
            dependencies=tuple(dependencies),
            startup_hook=startup_hook,
            shutdown_hook=shutdown_hook,
        )
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


__all__ = (
    "Application",
    "ApplicationState",
    "LifecycleHook",
    "LingShu",
)
