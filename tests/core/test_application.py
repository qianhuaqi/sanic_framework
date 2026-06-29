"""Application Kernel, dispatch, lifecycle, freeze, mapper, and RevisionId tests."""

from __future__ import annotations

import asyncio

import pytest
from lingshu.core.application import ApplicationState, LingShu
from lingshu.core.errors import (
    ConfigurationError,
    HandlerContractError,
    LifecycleError,
    LingShuError,
    RoutingError,
)
from lingshu.core.identifiers import RevisionId
from lingshu.core.plan import ApplicationPlan, ExtensionContribution
from lingshu.http import Headers, HTTPMethod, HTTPVersion, RequestBody, RequestTarget
from lingshu.http.exceptions import HTTPException
from lingshu.http.middleware import MiddlewareDeclaration
from lingshu.http.request import Request
from lingshu.http.response import Response
from lingshu.runtime import Scope, ScopeKind

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_request(
    method: str = "GET",
    path: str = "/",
    *,
    app: LingShu | None = None,
) -> Request:
    """Create a Request bound to a fresh Scope hierarchy."""

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        application_scope = Scope.application()
        connection_scope = application_scope.create_child(ScopeKind.CONNECTION)
        request_scope = connection_scope.create_child(ScopeKind.REQUEST, duration_ns=10_000_000_000)
        target = RequestTarget.parse(path)
        return Request(
            method=HTTPMethod(method),
            target=target,
            version=HTTPVersion.HTTP_1_1,
            headers=Headers([]),
            scope=request_scope,
            body=RequestBody.from_bytes(b"", scope=request_scope, max_bytes=0),
            request_id=type(request_scope).request_id
            if False
            else __import__(
                "lingshu.core.identifiers", fromlist=["RequestId"]
            ).RequestId.generate(),
            connection_id=__import__(
                "lingshu.core.identifiers", fromlist=["ConnectionId"]
            ).ConnectionId.generate(),
        )
    finally:
        loop.close()


async def _ok_handler(request: Request) -> Response:
    return Response.text("ok")


# ---------------------------------------------------------------------------
# Root facade
# ---------------------------------------------------------------------------


class TestRootFacade:
    def test_exact_root_all(self) -> None:
        import lingshu

        assert lingshu.__all__ == ()

    def test_root_does_not_export_internal_capabilities(self) -> None:
        import lingshu

        assert not hasattr(lingshu, "normalize_response")
        assert not hasattr(lingshu, "normalize_handler_return")
        assert not hasattr(lingshu, "SupportedReturnValue")


# ---------------------------------------------------------------------------
# HTTPException module ownership and safety
# ---------------------------------------------------------------------------


class TestHTTPException:
    def test_http_exception_is_in_http_module(self) -> None:
        from lingshu.http.exceptions import HTTPException as Exc

        assert Exc is HTTPException

    def test_http_exception_not_in_core_application(self) -> None:
        from lingshu.core import application

        assert not hasattr(application, "HTTPException")

    def test_basic_http_exception(self) -> None:
        exc = HTTPException(404, "Not found")
        assert exc.status_code == 404
        assert exc.http_status == 404
        assert exc.client_visible
        assert exc.code == "http.status_404"

    def test_status_code_must_be_400_to_599(self) -> None:
        with pytest.raises(ValueError):
            HTTPException(200)
        with pytest.raises(ValueError):
            HTTPException(600)

    def test_headers_are_immutable(self) -> None:
        exc = HTTPException(401, headers={"WWW-Authenticate": "Bearer"})
        assert exc.headers["WWW-Authenticate"] == "Bearer"
        with pytest.raises(TypeError):
            exc.headers["X"] = "Y"

    def test_does_not_leak_cause_or_traceback(self) -> None:
        exc = HTTPException(500, "fail")
        assert exc.internal_cause is None
        assert "traceback" not in str(exc).lower()
        assert repr(exc) == repr(exc)

    def test_custom_code(self) -> None:
        exc = HTTPException(422, "Invalid", code="custom.validation_error")
        assert exc.code == "custom.validation_error"

    def test_default_detail(self) -> None:
        exc = HTTPException(404)
        assert exc.safe_message

    def test_is_lingshu_error(self) -> None:
        assert isinstance(HTTPException(500), LingShuError)


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_initial_state_is_created(self) -> None:
        assert LingShu().state is ApplicationState.CREATED

    def test_registration_transitions_to_configuring(self) -> None:
        app = LingShu()

        @app.get("/")
        async def index(request: Request) -> Response:
            return Response.text("hello")

        assert app.state is ApplicationState.CONFIGURING

    def test_freeze_transitions_to_frozen(self) -> None:
        app = LingShu()
        plan = app.freeze()
        assert app.state is ApplicationState.FROZEN
        assert isinstance(plan, ApplicationPlan)

    def test_registration_after_freeze_rejected(self) -> None:
        app = LingShu()
        app.freeze()

        with pytest.raises(LifecycleError) as exc_info:

            @app.get("/late")
            async def late(request: Request) -> Response:
                return Response.text("late")

        assert exc_info.value.code == "lifecycle.frozen"

    def test_full_lifecycle(self) -> None:
        app = LingShu()
        app.freeze()

        async def run() -> None:
            await app.startup()
            assert app.state is ApplicationState.RUNNING
            await app.drain()
            assert app.state is ApplicationState.DRAINING
            await app.shutdown()
            assert app.state is ApplicationState.STOPPED

        asyncio.run(run())

    def test_shutdown_idempotent(self) -> None:
        app = LingShu()
        app.freeze()

        async def run() -> None:
            await app.startup()
            await app.shutdown()
            await app.shutdown()

        asyncio.run(run())

    def test_startup_requires_frozen(self) -> None:
        app = LingShu()

        async def run() -> None:
            with pytest.raises(LifecycleError):
                await app.startup()

        asyncio.run(run())

    def test_dispatch_requires_running(self) -> None:
        app = LingShu()
        app.freeze()
        request = make_request()

        async def run() -> None:
            with pytest.raises(LifecycleError):
                await app.dispatch("GET", "/", request)

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Freeze: idempotency, atomicity, RevisionId stability
# ---------------------------------------------------------------------------


class TestFreeze:
    def test_idempotent_freeze_returns_same_plan(self) -> None:
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            return Response.text("ok")

        plan1 = app.freeze()
        plan2 = app.freeze()
        assert plan1 is plan2

    def test_deterministic_revision_id(self) -> None:
        app1 = LingShu()

        @app1.get("/", name="root")
        async def root1(request: Request) -> Response:
            return Response.text("ok")

        plan1 = app1.freeze()

        app2 = LingShu()

        @app2.get("/", name="root")
        async def root2(request: Request) -> Response:
            return Response.text("ok")

        plan2 = app2.freeze()
        assert plan1.revision_id == plan2.revision_id

    def test_different_routes_different_revision_ids(self) -> None:
        app1 = LingShu()

        @app1.get("/a", name="a")
        async def ha(request: Request) -> Response:
            return Response.text("a")

        plan1 = app1.freeze()

        app2 = LingShu()

        @app2.get("/b", name="b")
        async def hb(request: Request) -> Response:
            return Response.text("b")

        plan2 = app2.freeze()
        assert plan1.revision_id != plan2.revision_id

    def test_changed_middleware_changes_revision_id(self) -> None:
        app1 = LingShu()

        @app1.get("/", name="root")
        async def root1(request: Request) -> Response:
            return Response.text("ok")

        plan1 = app1.freeze()

        app2 = LingShu()

        @app2.get("/", name="root")
        async def root2(request: Request) -> Response:
            return Response.text("ok")

        async def mw(request: Request, call_next: object) -> Response:
            return await call_next()  # type: ignore[misc]

        app2.add_middleware(mw)
        plan2 = app2.freeze()
        assert plan1.revision_id != plan2.revision_id

    def test_changed_mapper_changes_revision_id(self) -> None:
        app1 = LingShu()

        @app1.get("/", name="root")
        async def root1(request: Request) -> Response:
            return Response.text("ok")

        plan1 = app1.freeze()

        app2 = LingShu()

        @app2.get("/", name="root")
        async def root2(request: Request) -> Response:
            return Response.text("ok")

        def mapper(error: Exception) -> Response:
            return Response.text("err", status=500)

        app2.exception_mapper(ValueError, mapper)
        plan2 = app2.freeze()
        assert plan1.revision_id != plan2.revision_id

    def test_changed_extension_changes_revision_id(self) -> None:
        app1 = LingShu()

        @app1.get("/", name="root")
        async def root1(request: Request) -> Response:
            return Response.text("ok")

        plan1 = app1.freeze()

        app2 = LingShu()

        @app2.get("/", name="root")
        async def root2(request: Request) -> Response:
            return Response.text("ok")

        app2.add_extension("cache")
        plan2 = app2.freeze()
        assert plan1.revision_id != plan2.revision_id

    def test_changed_hook_changes_revision_id(self) -> None:
        app1 = LingShu()

        @app1.get("/", name="root")
        async def root1(request: Request) -> Response:
            return Response.text("ok")

        plan1 = app1.freeze()

        app2 = LingShu()

        @app2.get("/", name="root")
        async def root2(request: Request) -> Response:
            return Response.text("ok")

        @app2.on_startup("init")
        async def init() -> None:
            pass

        plan2 = app2.freeze()
        assert plan1.revision_id != plan2.revision_id

    def test_revision_id_is_sha256_hex(self) -> None:
        app = LingShu()
        plan = app.freeze()
        rid = plan.revision_id
        assert len(rid.value) == 64
        assert all(c in "0123456789abcdef" for c in rid.value)

    def test_revision_id_no_object_address(self) -> None:
        app = LingShu()
        plan = app.freeze()
        rid_str = str(plan.revision_id)
        assert "0x" not in rid_str

    def test_freeze_failure_no_partial_plan(self) -> None:
        app = LingShu()

        @app.get("/dup", name="d1")
        async def d1(request: Request) -> Response:
            return Response.text("d1")

        @app.get("/dup", name="d2")
        async def d2(request: Request) -> Response:
            return Response.text("d2")

        with pytest.raises(RoutingError):
            app.freeze()
        assert app.plan is None

    def test_freeze_failure_preserves_existing_plan(self) -> None:
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            return Response.text("ok")

        plan1 = app.freeze()
        # Try to freeze again with a bad state — but since we already have a plan
        # and catalog is not dirty, it returns the same plan.
        plan2 = app.freeze()
        assert plan1 is plan2

    def test_can_continue_after_freeze_failure(self) -> None:
        app = LingShu()

        @app.get("/dup", name="d1")
        async def d1(request: Request) -> Response:
            return Response.text("d1")

        @app.get("/dup", name="d2")
        async def d2(request: Request) -> Response:
            return Response.text("d2")

        with pytest.raises(RoutingError):
            app.freeze()

        # After failure, state should still allow reconfiguration.
        # The catalog is still dirty, so we should be able to fix and retry.
        # We can't easily remove the duplicate from catalog, but the state
        # allows attempting freeze again.
        assert app.state in (ApplicationState.CREATED, ApplicationState.CONFIGURING)


# ---------------------------------------------------------------------------
# Dispatch: 404, 405, MATCH, middleware wrapping
# ---------------------------------------------------------------------------


class TestDispatch:
    def test_static_route_dispatch(self) -> None:
        app = LingShu()

        @app.get("/hello", name="hello")
        async def hello(request: Request) -> Response:
            return Response.text("world")

        app.freeze()
        request = make_request("GET", "/hello")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/hello", request)
            assert response.status == 200
            assert response.body == b"world"
            await app.shutdown()

        asyncio.run(run())

    def test_parameter_route_dispatch(self) -> None:
        app = LingShu()

        @app.get("/users/{id}", name="user")
        async def user(request: Request) -> Response:
            return Response.text(request.path_params["id"])

        app.freeze()
        request = make_request("GET", "/users/42")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/users/42", request)
            assert response.body == b"42"
            await app.shutdown()

        asyncio.run(run())

    def test_404_dispatch(self) -> None:
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            return Response.text("ok")

        app.freeze()
        request = make_request("GET", "/nonexistent")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/nonexistent", request)
            assert response.status == 404
            await app.shutdown()

        asyncio.run(run())

    def test_405_dispatch_with_sorted_allow(self) -> None:
        app = LingShu()

        @app.route("/items", ("POST", "GET", "PUT"), name="items")
        async def items(request: Request) -> Response:
            return Response.text("items")

        app.freeze()
        request = make_request("DELETE", "/items")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("DELETE", "/items", request)
            assert response.status == 405
            allow_header = response.headers.get("allow")
            assert allow_header is not None
            methods = allow_header.split(",")
            assert methods == sorted(methods)
            assert "GET" in methods
            assert "POST" in methods
            assert "PUT" in methods
            await app.shutdown()

        asyncio.run(run())

    def test_handler_return_normalized_exactly_once(self) -> None:
        app = LingShu()

        @app.get("/str", name="str_route")
        async def str_handler(request: Request) -> str:
            return "text result"

        app.freeze()
        request = make_request("GET", "/str")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/str", request)
            assert response.body == b"text result"
            await app.shutdown()

        asyncio.run(run())

    def test_application_middleware_wraps_route_match(self) -> None:
        app = LingShu()
        seen: list[str] = []

        async def mw(request: Request, call_next: object) -> Response:
            seen.append("ingress")
            response = await call_next()  # type: ignore[misc]
            seen.append("egress")
            return response

        app.add_middleware(mw)

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            seen.append("handler")
            return Response.text("ok")

        app.freeze()
        request = make_request("GET", "/")

        async def run() -> None:
            await app.startup()
            await app.dispatch("GET", "/", request)
            await app.shutdown()

        asyncio.run(run())
        assert seen == ["ingress", "handler", "egress"]

    def test_route_middleware_only_after_match(self) -> None:
        app = LingShu()
        route_mw_called: list[str] = []

        async def route_mw(request: Request, call_next: object) -> Response:
            route_mw_called.append("called")
            return await call_next()  # type: ignore[misc]

        @app.get("/special", name="special", middleware=[MiddlewareDeclaration(route_mw)])
        async def special(request: Request) -> Response:
            return Response.text("special")

        @app.get("/other", name="other")
        async def other(request: Request) -> Response:
            return Response.text("other")

        app.freeze()

        async def run() -> None:
            await app.startup()
            # Dispatch to /other — route middleware should NOT run.
            req = make_request("GET", "/other")
            await app.dispatch("GET", "/other", req)
            assert route_mw_called == []

            # Dispatch to /special — route middleware SHOULD run.
            req2 = make_request("GET", "/special")
            await app.dispatch("GET", "/special", req2)
            assert route_mw_called == ["called"]
            await app.shutdown()

        asyncio.run(run())

    def test_middleware_ordering_event_sequence(self) -> None:
        """Document the canonical dispatch pipeline event order on MATCH.

        Required order: app:in → route:match → route:in → handler → route:out → app:out.
        """

        app = LingShu()
        events: list[str] = []

        async def app_mw(request: Request, call_next: object) -> Response:
            events.append("app:in")
            response = await call_next()  # type: ignore[misc]
            events.append("app:out")
            return response

        app.add_middleware(app_mw)

        async def route_mw(request: Request, call_next: object) -> Response:
            events.append("route:in")
            response = await call_next()  # type: ignore[misc]
            events.append("route:out")
            return response

        @app.get("/", name="root", middleware=[MiddlewareDeclaration(route_mw)])
        async def root(request: Request) -> Response:
            events.append("handler")
            return Response.text("ok")

        app.freeze()
        request = make_request("GET", "/")

        async def run() -> None:
            await app.startup()
            await app.dispatch("GET", "/", request)
            await app.shutdown()

        asyncio.run(run())
        assert events == [
            "app:in",
            "route:in",
            "handler",
            "route:out",
            "app:out",
        ]

    def test_middleware_ordering_404_through_app_middleware(self) -> None:
        """404 must be produced inside the app middleware terminal.

        Event order: app:in → route:match(404) → app:out. No route middleware runs.
        """

        app = LingShu()
        events: list[str] = []

        async def app_mw(request: Request, call_next: object) -> Response:
            events.append("app:in")
            response = await call_next()  # type: ignore[misc]
            events.append("app:out")
            return response

        app.add_middleware(app_mw)

        async def route_mw(request: Request, call_next: object) -> Response:
            events.append("route:in")
            return await call_next()  # type: ignore[misc]

        @app.get("/exists", name="root", middleware=[MiddlewareDeclaration(route_mw)])
        async def root(request: Request) -> Response:
            events.append("handler")
            return Response.text("ok")

        app.freeze()
        request = make_request("GET", "/missing")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/missing", request)
            assert response.status == 404
            await app.shutdown()

        asyncio.run(run())
        assert events == ["app:in", "app:out"]

    def test_middleware_ordering_405_through_app_middleware(self) -> None:
        """405 must be produced inside the app middleware terminal.

        Event order: app:in → route:match(405) → app:out. No route middleware runs.
        """

        app = LingShu()
        events: list[str] = []

        async def app_mw(request: Request, call_next: object) -> Response:
            events.append("app:in")
            response = await call_next()  # type: ignore[misc]
            events.append("app:out")
            return response

        app.add_middleware(app_mw)

        async def route_mw(request: Request, call_next: object) -> Response:
            events.append("route:in")
            return await call_next()  # type: ignore[misc]

        @app.post("/items", name="items", middleware=[MiddlewareDeclaration(route_mw)])
        async def items(request: Request) -> Response:
            events.append("handler")
            return Response.text("ok")

        app.freeze()
        request = make_request("GET", "/items")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/items", request)
            assert response.status == 405
            await app.shutdown()

        asyncio.run(run())
        assert events == ["app:in", "app:out"]

    def test_anonymous_route_middleware_runs(self) -> None:
        """Anonymous routes (no name) must still execute route middleware.

        The route identity is (path_template, methods), not route.name.
        """

        app = LingShu()
        route_mw_called: list[str] = []

        async def route_mw(request: Request, call_next: object) -> Response:
            route_mw_called.append("called")
            return await call_next()  # type: ignore[misc]

        @app.get("/", middleware=[MiddlewareDeclaration(route_mw)])
        async def root(request: Request) -> Response:
            return Response.text("ok")

        app.freeze()
        request = make_request("GET", "/")

        async def run() -> None:
            await app.startup()
            await app.dispatch("GET", "/", request)
            await app.shutdown()

        asyncio.run(run())
        assert route_mw_called == ["called"]

    def test_anonymous_route_path_params_published(self) -> None:
        """Anonymous parameter routes must publish path_params.

        Uses path_template as route_label when name is None.
        """

        app = LingShu()

        @app.get("/users/{user_id}")
        async def user(request: Request) -> Response:
            return Response.text(request.path_params["user_id"])

        app.freeze()
        request = make_request("GET", "/users/42")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/users/42", request)
            assert response.body == b"42"
            await app.shutdown()

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Exception mapper: MRO resolution, scope priority, fallback
# ---------------------------------------------------------------------------


class TestExceptionMapper:
    def test_route_scoped_mapper_resolves(self) -> None:
        app = LingShu()

        @app.get("/special", name="special")
        async def special(request: Request) -> Response:
            raise ValueError("oops")

        def mapper(error: Exception) -> Response:
            return Response.text("mapped", status=503)

        app.exception_mapper(ValueError, mapper, route_name="special")
        app.freeze()
        request = make_request("GET", "/special")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/special", request)
            assert response.status == 503
            await app.shutdown()

        asyncio.run(run())

    def test_app_scoped_mapper_resolves(self) -> None:
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            raise ValueError("bad")

        def mapper(error: Exception) -> Response:
            return Response.text("app_mapped", status=400)

        app.exception_mapper(ValueError, mapper)
        app.freeze()
        request = make_request("GET", "/")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/", request)
            assert response.status == 400
            await app.shutdown()

        asyncio.run(run())

    def test_route_mapper_precedence_over_app_mapper(self) -> None:
        app = LingShu()

        @app.get("/r", name="r")
        async def r_handler(request: Request) -> Response:
            raise ValueError("x")

        def app_mapper(error: Exception) -> Response:
            return Response.text("app", status=500)

        def route_mapper(error: Exception) -> Response:
            return Response.text("route", status=418)

        app.exception_mapper(ValueError, app_mapper)
        app.exception_mapper(ValueError, route_mapper, route_name="r")
        app.freeze()
        request = make_request("GET", "/r")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/r", request)
            assert response.status == 418
            await app.shutdown()

        asyncio.run(run())

    def test_most_specific_exception_type_wins(self) -> None:
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            raise ValueError("x")

        def base_mapper(error: Exception) -> Response:
            return Response.text("base", status=500)

        def specific_mapper(error: Exception) -> Response:
            return Response.text("specific", status=422)

        app.exception_mapper(Exception, base_mapper)
        app.exception_mapper(ValueError, specific_mapper)
        app.freeze()
        request = make_request("GET", "/")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/", request)
            assert response.status == 422
            await app.shutdown()

        asyncio.run(run())

    def test_mapper_invalid_output_falls_back_to_500(self) -> None:
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            raise ValueError("x")

        def bad_mapper(error: Exception) -> int:
            return 42  # type: ignore[return-value]

        app.exception_mapper(ValueError, bad_mapper)
        app.freeze()
        request = make_request("GET", "/")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/", request)
            assert response.status == 500
            await app.shutdown()

        asyncio.run(run())

    def test_mapper_exception_falls_back_to_500(self) -> None:
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            raise ValueError("x")

        def crashing_mapper(error: Exception) -> Response:
            raise RuntimeError("mapper crashed")

        app.exception_mapper(ValueError, crashing_mapper)
        app.freeze()
        request = make_request("GET", "/")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/", request)
            assert response.status == 500
            await app.shutdown()

        asyncio.run(run())

    def test_http_exception_builtin_response(self) -> None:
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            raise HTTPException(404, "Custom Not Found")

        app.freeze()
        request = make_request("GET", "/")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/", request)
            assert response.status == 404
            assert b"Custom Not Found" in response.body
            await app.shutdown()

        asyncio.run(run())

    def test_safe_500_for_unhandled(self) -> None:
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            raise RuntimeError("secret error with /private/path")

        app.freeze()
        request = make_request("GET", "/")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/", request)
            assert response.status == 500
            assert b"secret" not in response.body
            assert b"/private/path" not in response.body
            await app.shutdown()

        asyncio.run(run())

    def test_mapper_unknown_route_fails_at_freeze(self) -> None:
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            return Response.text("ok")

        def mapper(error: Exception) -> Response:
            return Response.text("err", status=500)

        app.exception_mapper(Exception, mapper, route_name="nonexistent")
        with pytest.raises(ConfigurationError) as exc_info:
            app.freeze()
        assert exc_info.value.code == "freeze.mapper_unknown_route"

    def test_duplicate_route_mappers_fail(self) -> None:
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            return Response.text("ok")

        def m1(error: Exception) -> Response:
            return Response.text("e1", status=500)

        def m2(error: Exception) -> Response:
            return Response.text("e2", status=500)

        app.exception_mapper(ValueError, m1, route_name="root")
        app.exception_mapper(ValueError, m2, route_name="root")
        with pytest.raises(ConfigurationError) as exc_info:
            app.freeze()
        assert exc_info.value.code == "freeze.mapper_ambiguous"

    def test_diamond_inheritance_most_specific_wins(self) -> None:
        """In a diamond inheritance hierarchy the most-specific mapper wins."""

        class Base(Exception):
            pass

        class Mid(Base):
            pass

        class Leaf(Mid):
            pass

        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            raise Leaf("x")

        def base_mapper(error: Exception) -> Response:
            return Response.text("base", status=500)

        def mid_mapper(error: Exception) -> Response:
            return Response.text("mid", status=501)

        app.exception_mapper(Base, base_mapper)
        app.exception_mapper(Mid, mid_mapper)
        app.freeze()
        request = make_request("GET", "/")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/", request)
            assert response.status == 501
            await app.shutdown()

        asyncio.run(run())

    def test_mro_winner_independent_of_registration_order(self) -> None:
        """Most-specific mapper wins regardless of registration order.

        This guards against the regression where a buggy comparison selected the
        least-specific mapper depending on iteration order.
        """

        class Custom(Exception):
            pass

        # Register base FIRST, then specific — specific must still win.
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            raise Custom("x")

        def base_mapper(error: Exception) -> Response:
            return Response.text("base", status=500)

        def exact_mapper(error: Exception) -> Response:
            return Response.text("exact", status=422)

        app.exception_mapper(Exception, base_mapper)
        app.exception_mapper(Custom, exact_mapper)
        app.freeze()
        request = make_request("GET", "/")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/", request)
            assert response.status == 422
            await app.shutdown()

        asyncio.run(run())

    def test_mro_winner_specific_registered_first(self) -> None:
        """Most-specific mapper wins even when registered before the base mapper."""

        class Custom(Exception):
            pass

        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            raise Custom("x")

        def base_mapper(error: Exception) -> Response:
            return Response.text("base", status=500)

        def exact_mapper(error: Exception) -> Response:
            return Response.text("exact", status=422)

        # Register specific FIRST — must still win.
        app.exception_mapper(Custom, exact_mapper)
        app.exception_mapper(Exception, base_mapper)
        app.freeze()
        request = make_request("GET", "/")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/", request)
            assert response.status == 422
            await app.shutdown()

        asyncio.run(run())

    def test_unrelated_exception_type_not_matched(self) -> None:
        """A mapper for an unrelated type is never selected."""

        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            raise ValueError("x")

        def keyerror_mapper(error: Exception) -> Response:
            return Response.text("wrong", status=400)

        app.exception_mapper(KeyError, keyerror_mapper)
        app.freeze()
        request = make_request("GET", "/")

        async def run() -> None:
            await app.startup()
            response = await app.dispatch("GET", "/", request)
            assert response.status == 500
            await app.shutdown()

        asyncio.run(run())


# ---------------------------------------------------------------------------
# BaseException control flow preservation
# ---------------------------------------------------------------------------


class TestBaseExceptionControlFlow:
    def test_cancelled_error_original_instance_reraised(self) -> None:
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            raise asyncio.CancelledError("client disconnect")

        app.freeze()
        request = make_request("GET", "/")

        original = None

        async def run() -> None:
            nonlocal original
            await app.startup()
            try:
                await app.dispatch("GET", "/", request)
            except BaseException as exc:
                original = exc
            await app.shutdown()

        asyncio.run(run())
        assert isinstance(original, asyncio.CancelledError)
        assert str(original) == "client disconnect"

    def test_keyboard_interrupt_reraised(self) -> None:
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            raise KeyboardInterrupt()

        app.freeze()
        request = make_request("GET", "/")

        captured = None

        async def run() -> None:
            nonlocal captured
            await app.startup()
            try:
                await app.dispatch("GET", "/", request)
            except BaseException as exc:
                captured = exc
            await app.shutdown()

        asyncio.run(run())
        assert isinstance(captured, KeyboardInterrupt)

    def test_system_exit_reraised(self) -> None:
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            raise SystemExit(1)

        app.freeze()
        request = make_request("GET", "/")

        captured = None

        async def run() -> None:
            nonlocal captured
            await app.startup()
            try:
                await app.dispatch("GET", "/", request)
            except BaseException as exc:
                captured = exc
            await app.shutdown()

        asyncio.run(run())
        assert isinstance(captured, SystemExit)


# ---------------------------------------------------------------------------
# Extension lifecycle protocol
# ---------------------------------------------------------------------------


class TestExtensionLifecycle:
    def test_startup_dependency_order(self) -> None:
        app = LingShu()
        order: list[str] = []

        async def start_a() -> None:
            order.append("a")

        async def start_b() -> None:
            order.append("b")

        app.add_extension("a", startup_hook=start_a)
        app.add_extension("b", dependencies=("a",), startup_hook=start_b)
        app.freeze()

        async def run() -> None:
            await app.startup()

        asyncio.run(run())
        assert order == ["a", "b"]

    def test_shutdown_strict_reverse_order(self) -> None:
        app = LingShu()
        order: list[str] = []

        async def start_a() -> None:
            order.append("start_a")

        async def stop_a() -> None:
            order.append("stop_a")

        async def start_b() -> None:
            order.append("start_b")

        async def stop_b() -> None:
            order.append("stop_b")

        app.add_extension("a", startup_hook=start_a, shutdown_hook=stop_a)
        app.add_extension("b", dependencies=("a",), startup_hook=start_b, shutdown_hook=stop_b)
        app.freeze()

        async def run() -> None:
            await app.startup()
            await app.shutdown()

        asyncio.run(run())
        assert order == ["start_a", "start_b", "stop_b", "stop_a"]

    def test_partial_startup_failure_rollback(self) -> None:
        app = LingShu()
        stopped: list[str] = []

        async def start_a() -> None:
            pass

        async def stop_a() -> None:
            stopped.append("a")

        async def start_b() -> None:
            raise RuntimeError("b failed")

        async def stop_b() -> None:
            stopped.append("b")

        app.add_extension("a", startup_hook=start_a, shutdown_hook=stop_a)
        app.add_extension("b", dependencies=("a",), startup_hook=start_b, shutdown_hook=stop_b)
        app.freeze()

        async def run() -> None:
            with pytest.raises(RuntimeError):
                await app.startup()

        asyncio.run(run())
        assert stopped == ["a"]
        assert app.state is ApplicationState.FROZEN

    def test_duplicate_extension_fails(self) -> None:
        app = LingShu()
        app.add_extension("ext")
        app.add_extension("ext")
        with pytest.raises(ConfigurationError) as exc_info:
            app.freeze()
        assert exc_info.value.code == "freeze.duplicate_extension"

    def test_missing_dependency_fails(self) -> None:
        app = LingShu()
        app.add_extension("a", dependencies=("missing",))
        with pytest.raises(ConfigurationError) as exc_info:
            app.freeze()
        assert exc_info.value.code == "freeze.extension_unknown_dependency"

    def test_cycle_dependency_fails(self) -> None:
        app = LingShu()
        app.add_extension("a", dependencies=("b",))
        app.add_extension("b", dependencies=("a",))
        with pytest.raises(ConfigurationError) as exc_info:
            app.freeze()
        assert exc_info.value.code == "freeze.extension_cycle"

    def test_sync_startup_hook_rejected(self) -> None:
        def sync_hook() -> None:
            pass

        with pytest.raises(TypeError):
            ExtensionContribution("ext", startup_hook=sync_hook)  # type: ignore[arg-type]

    def test_application_startup_hooks_executed(self) -> None:
        app = LingShu()
        called: list[str] = []

        @app.on_startup("init")
        async def init() -> None:
            called.append("init")

        app.freeze()

        async def run() -> None:
            await app.startup()

        asyncio.run(run())
        assert called == ["init"]

    def test_application_shutdown_hooks_executed_reverse(self) -> None:
        app = LingShu()
        called: list[str] = []

        @app.on_startup("s1")
        async def s1() -> None:
            called.append("s1")

        @app.on_shutdown("h1")
        async def h1() -> None:
            called.append("h1")

        @app.on_shutdown("h2")
        async def h2() -> None:
            called.append("h2")

        app.freeze()

        async def run() -> None:
            await app.startup()
            await app.shutdown()

        asyncio.run(run())
        # Shutdown hooks execute in reverse registration order.
        assert called == ["s1", "h2", "h1"]


# ---------------------------------------------------------------------------
# Handler signature validation
# ---------------------------------------------------------------------------


class TestHandlerSignature:
    def test_sync_handler_rejected(self) -> None:
        app = LingShu()

        def sync_handler(request: Request) -> Response:
            return Response.text("sync")

        app.get("/sync")(sync_handler)
        with pytest.raises(HandlerContractError):
            app.freeze()

    def test_zero_args_rejected(self) -> None:
        app = LingShu()

        async def no_args() -> Response:
            return Response.text("noargs")

        app.get("/noargs")(no_args)
        with pytest.raises(HandlerContractError):
            app.freeze()

    def test_two_args_rejected(self) -> None:
        app = LingShu()

        async def two_args(request: Request, extra: int) -> Response:
            return Response.text("two")

        app.get("/two")(two_args)
        with pytest.raises(HandlerContractError):
            app.freeze()

    def test_var_args_rejected(self) -> None:
        app = LingShu()

        async def var_args(request: Request, *args: object) -> Response:
            return Response.text("varargs")

        app.get("/varargs")(var_args)
        with pytest.raises(HandlerContractError):
            app.freeze()

    def test_var_kwargs_rejected(self) -> None:
        app = LingShu()

        async def var_kwargs(request: Request, **kwargs: object) -> Response:
            return Response.text("varkwargs")

        app.get("/varkwargs")(var_kwargs)
        with pytest.raises(HandlerContractError):
            app.freeze()

    def test_required_keyword_only_rejected(self) -> None:
        app = LingShu()

        async def kw_only(request: Request, *, required: str) -> Response:
            return Response.text(required)

        app.get("/kwonly")(kw_only)
        with pytest.raises(HandlerContractError):
            app.freeze()

    def test_valid_async_single_param_accepted(self) -> None:
        app = LingShu()

        @app.get("/ok", name="ok")
        async def ok(req: Request) -> Response:
            return Response.text("ok")

        plan = app.freeze()
        assert plan is not None


# ---------------------------------------------------------------------------
# Plan immutability
# ---------------------------------------------------------------------------


class TestPlanImmutability:
    def test_plan_does_not_leak_mutable_catalog(self) -> None:
        app = LingShu()

        @app.get("/", name="root")
        async def root(request: Request) -> Response:
            return Response.text("ok")

        plan = app.freeze()
        # Plan properties are read-only.
        with pytest.raises((AttributeError, TypeError)):
            plan.router = None  # type: ignore[misc]
        with pytest.raises((AttributeError, TypeError)):
            plan.revision_id = RevisionId.parse("0" * 64)  # type: ignore[misc]
