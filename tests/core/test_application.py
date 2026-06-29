"""Application Kernel, Revision, freeze, lifecycle, and public API tests."""

from __future__ import annotations

import asyncio

import pytest
from lingshu import HTTPException, LingShu, Request, Response
from lingshu.core.application import Application, ApplicationState
from lingshu.core.errors import ConfigurationError, LifecycleError, LingShuError, RoutingError
from lingshu.core.identifiers import RevisionId
from lingshu.core.plan import ApplicationPlan

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


async def _ok_handler(request: Request) -> Response:
    return Response.text("ok")


async def _text_handler(request: Request) -> str:
    return "hello"


async def _boom_handler(request: Request) -> Response:
    raise HTTPException(418, "I am a teapot")


async def _internal_error_handler(request: Request) -> Response:
    raise RuntimeError("boom")


async def _return_none_handler(request: Request) -> None:
    return None  # type: ignore[return-value]


async def _sync_handler(request: Request) -> Response:  # pragma: no cover
    return Response.text("sync")


def _sync_non_async(request: Request) -> Response:  # pragma: no cover
    return Response.text("not async")


async def _two_param_handler(request: Request, extra: int = 0) -> Response:  # pragma: no cover
    return Response.text("two")


# --------------------------------------------------------------------------
# Lifecycle state transitions
# --------------------------------------------------------------------------


class TestLifecycleTransitions:
    def test_initial_state_is_created(self) -> None:
        app = LingShu()
        assert app.state is ApplicationState.CREATED

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

    def test_registration_after_freeze_is_rejected(self) -> None:
        app = LingShu()
        app.freeze()

        with pytest.raises(LifecycleError) as exc_info:

            @app.get("/late")
            async def late(request: Request) -> Response:
                return Response.text("late")

        assert exc_info.value.code == "lifecycle.frozen"

    def test_startup_requires_frozen_state(self) -> None:
        app = LingShu()

        async def run() -> None:
            with pytest.raises(LifecycleError) as exc_info:
                await app.startup()
            assert exc_info.value.code == "lifecycle.invalid_state"

        asyncio.run(run())

    @pytest.mark.parametrize(
        "method",
        ["startup", "drain", "shutdown"],
    )
    def test_lifecycle_methods_on_unfrozen_app_reject(self, method: str) -> None:
        app = LingShu()

        async def run() -> None:
            with pytest.raises(LifecycleError):
                await getattr(app, method)()

        asyncio.run(run())

    def test_full_lifecycle_startup_drain_shutdown(self) -> None:
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

    def test_shutdown_is_idempotent(self) -> None:
        app = LingShu()
        app.freeze()

        async def run() -> None:
            await app.startup()
            await app.shutdown()
            assert app.state is ApplicationState.STOPPED
            await app.shutdown()
            assert app.state is ApplicationState.STOPPED

        asyncio.run(run())

    def test_startup_is_idempotent_when_running(self) -> None:
        app = LingShu()
        app.freeze()

        async def run() -> None:
            await app.startup()
            assert app.state is ApplicationState.RUNNING
            await app.startup()
            assert app.state is ApplicationState.RUNNING

        asyncio.run(run())


# --------------------------------------------------------------------------
# Freeze: idempotency, atomicity, immutability
# --------------------------------------------------------------------------


class TestFreeze:
    def test_freeze_is_idempotent_for_unchanged_revision(self) -> None:
        app = LingShu()

        @app.get("/")
        async def index(request: Request) -> Response:
            return Response.text("hello")

        plan1 = app.freeze()
        plan2 = app.freeze()
        assert plan1 is plan2
        assert plan1.revision_id == plan2.revision_id

    def test_freeze_produces_deterministic_revision_id(self) -> None:
        app1 = LingShu()

        @app1.get("/")
        async def index1(request: Request) -> Response:
            return Response.text("hello")

        plan1 = app1.freeze()

        app2 = LingShu()

        @app2.get("/")
        async def index2(request: Request) -> Response:
            return Response.text("hello")

        plan2 = app2.freeze()
        assert plan1.revision_id == plan2.revision_id

    def test_different_routes_produce_different_revision_ids(self) -> None:
        app1 = LingShu()

        @app1.get("/a")
        async def handler_a(request: Request) -> Response:
            return Response.text("a")

        plan1 = app1.freeze()

        app2 = LingShu()

        @app2.get("/b")
        async def handler_b(request: Request) -> Response:
            return Response.text("b")

        plan2 = app2.freeze()
        assert plan1.revision_id != plan2.revision_id

    def test_freeze_failure_publishes_no_partial_plan(self) -> None:
        app = LingShu()

        @app.get("/dup")
        async def first(request: Request) -> Response:
            return Response.text("first")

        @app.get("/dup")
        async def second(request: Request) -> Response:
            return Response.text("second")

        # Second registration with same path+method should fail at freeze.
        with pytest.raises(RoutingError):
            app.freeze()
        assert app.plan is None
        assert app.state is ApplicationState.CONFIGURING

    def test_plan_router_is_immutable_after_freeze(self) -> None:
        app = LingShu()

        @app.get("/")
        async def index(request: Request) -> Response:
            return Response.text("hello")

        plan = app.freeze()
        match = plan.router.match("GET", "/")
        assert match.kind.value == "match"

        with pytest.raises((AttributeError, TypeError)):
            plan.router._routes = ()  # type: ignore[misc]


# --------------------------------------------------------------------------
# Route registration via decorators
# --------------------------------------------------------------------------


class TestRouteRegistration:
    def test_get_decorator_registers_route(self) -> None:
        app = LingShu()

        @app.get("/users")
        async def users(request: Request) -> Response:
            return Response.text("users")

        plan = app.freeze()
        match = plan.router.match("GET", "/users")
        assert match.kind.value == "match"

    def test_multiple_methods_via_route(self) -> None:
        app = LingShu()

        @app.route("/items", ("GET", "POST"))
        async def items(request: Request) -> Response:
            return Response.text("items")

        plan = app.freeze()
        assert plan.router.match("GET", "/items").kind.value == "match"
        assert plan.router.match("POST", "/items").kind.value == "match"

    @pytest.mark.parametrize(
        ("decorator", "method"),
        [
            ("get", "GET"),
            ("post", "POST"),
            ("put", "PUT"),
            ("patch", "PATCH"),
            ("delete", "DELETE"),
            ("head", "HEAD"),
            ("options", "OPTIONS"),
        ],
    )
    def test_all_method_decorators(self, decorator: str, method: str) -> None:
        app = LingShu()
        getattr(app, decorator)("/test")(_ok_handler)
        plan = app.freeze()
        assert plan.router.match(method, "/test").kind.value == "match"

    def test_path_parameter_route_matches(self) -> None:
        app = LingShu()

        @app.get("/users/{id}")
        async def user_detail(request: Request) -> Response:
            return Response.text("detail")

        plan = app.freeze()
        match = plan.router.match("GET", "/users/42")
        assert match.kind.value == "match"
        assert match.path_params["id"] == "42"


# --------------------------------------------------------------------------
# Handler contract validation
# --------------------------------------------------------------------------


class TestHandlerContract:
    def test_sync_handler_rejected_at_freeze(self) -> None:
        app = LingShu()
        app.get("/sync")(_sync_non_async)
        with pytest.raises(Exception) as exc_info:
            app.freeze()
        assert "async" in str(exc_info.value).lower()

    def test_two_parameter_handler_rejected_at_freeze(self) -> None:
        app = LingShu()
        app.route("/two", ("GET",))(_two_param_handler)
        with pytest.raises(Exception) as exc_info:
            app.freeze()
        assert "one positional" in str(exc_info.value).lower()


# --------------------------------------------------------------------------
# Exception mapper resolution
# --------------------------------------------------------------------------


class TestExceptionMapper:
    def test_route_scoped_mapper_resolves(self) -> None:
        app = LingShu()

        @app.get("/special", name="special")
        async def special(request: Request) -> Response:
            raise RuntimeError("oops")

        def mapper(error: Exception) -> LingShuError:
            return HTTPException(503, "Service specific error")

        app.exception_mapper(mapper, route_name="special")
        plan = app.freeze()
        resolved = plan.resolve_exception(RuntimeError("oops"), "special")
        assert resolved.client_visible
        assert resolved.http_status == 503

    def test_application_scoped_mapper_resolves(self) -> None:
        app = LingShu()

        @app.get("/")
        async def index(request: Request) -> Response:
            return Response.text("ok")

        def mapper(error: Exception) -> LingShuError:
            return HTTPException(400, "Bad thing")

        app.exception_mapper(mapper)
        plan = app.freeze()
        resolved = plan.resolve_exception(ValueError("bad"), None)
        assert resolved.http_status == 400

    def test_http_exception_passes_through_when_no_mapper(self) -> None:
        app = LingShu()

        @app.get("/")
        async def index(request: Request) -> Response:
            return Response.text("ok")

        plan = app.freeze()
        http_exc = HTTPException(404, "Not found")
        resolved = plan.resolve_exception(http_exc, None)
        assert resolved is http_exc

    def test_unhandled_exception_maps_to_internal_error(self) -> None:
        app = LingShu()

        @app.get("/")
        async def index(request: Request) -> Response:
            return Response.text("ok")

        plan = app.freeze()
        resolved = plan.resolve_exception(RuntimeError("secret"), None)
        assert resolved.code == "internal.unhandled"
        assert not resolved.client_visible
        assert resolved.internal_cause is not None

    def test_route_mapper_takes_precedence_over_app_mapper(self) -> None:
        app = LingShu()

        @app.get("/route1", name="route1")
        async def route1(request: Request) -> Response:
            return Response.text("r1")

        def app_mapper(error: Exception) -> LingShuError:
            return HTTPException(500, "App fallback")

        def route_mapper(error: Exception) -> LingShuError:
            return HTTPException(418, "Route specific")

        app.exception_mapper(app_mapper)
        app.exception_mapper(route_mapper, route_name="route1")
        plan = app.freeze()
        resolved = plan.resolve_exception(RuntimeError("x"), "route1")
        assert resolved.http_status == 418

    def test_mapper_unknown_route_fails_at_freeze(self) -> None:
        app = LingShu()

        @app.get("/")
        async def index(request: Request) -> Response:
            return Response.text("ok")

        def mapper(error: Exception) -> LingShuError:
            return HTTPException(500, "error")

        app.exception_mapper(mapper, route_name="nonexistent")
        with pytest.raises(ConfigurationError) as exc_info:
            app.freeze()
        assert exc_info.value.code == "freeze.mapper_unknown_route"

    def test_duplicate_route_mappers_fail_at_freeze(self) -> None:
        app = LingShu()

        @app.get("/", name="home")
        async def home(request: Request) -> Response:
            return Response.text("home")

        def mapper1(error: Exception) -> LingShuError:
            return HTTPException(500, "e1")

        def mapper2(error: Exception) -> LingShuError:
            return HTTPException(500, "e2")

        app.exception_mapper(mapper1, route_name="home")
        app.exception_mapper(mapper2, route_name="home")
        with pytest.raises(ConfigurationError) as exc_info:
            app.freeze()
        assert exc_info.value.code == "freeze.mapper_ambiguous"

    def test_multiple_application_mappers_fail_at_freeze(self) -> None:
        app = LingShu()

        @app.get("/")
        async def index(request: Request) -> Response:
            return Response.text("ok")

        def mapper1(error: Exception) -> LingShuError:
            return HTTPException(500, "e1")

        def mapper2(error: Exception) -> LingShuError:
            return HTTPException(500, "e2")

        app.exception_mapper(mapper1)
        app.exception_mapper(mapper2)
        with pytest.raises(ConfigurationError) as exc_info:
            app.freeze()
        assert exc_info.value.code == "freeze.mapper_ambiguous"

    def test_mapper_failure_falls_back_safely(self) -> None:
        app = LingShu()

        @app.get("/")
        async def index(request: Request) -> Response:
            return Response.text("ok")

        def bad_mapper(error: Exception) -> LingShuError:
            raise RuntimeError("mapper itself broke")

        app.exception_mapper(bad_mapper)
        plan = app.freeze()
        resolved = plan.resolve_exception(ValueError("original"), None)
        assert resolved.code == "internal.mapper_failed"
        assert not resolved.client_visible

    def test_cancelled_error_not_converted_to_response(self) -> None:
        app = LingShu()

        @app.get("/")
        async def index(request: Request) -> Response:
            return Response.text("ok")

        plan = app.freeze()

        async def run() -> None:
            cancelled = asyncio.CancelledError("client disconnect")
            with pytest.raises(TypeError):
                plan.resolve_exception(cancelled, None)

        asyncio.run(run())

    def test_base_exception_not_converted(self) -> None:
        app = LingShu()

        @app.get("/")
        async def index(request: Request) -> Response:
            return Response.text("ok")

        plan = app.freeze()

        class CustomBase(BaseException):
            pass

        with pytest.raises(TypeError):
            plan.resolve_exception(CustomBase(), None)


# --------------------------------------------------------------------------
# Extension placeholder protocol
# --------------------------------------------------------------------------


class TestExtensions:
    def test_extension_dependency_resolution(self) -> None:
        app = LingShu()
        app.add_extension("b", dependencies=("a",))
        app.add_extension("a")
        plan = app.freeze()
        assert plan.extension_plan.startup_order.index("a") < \
            plan.extension_plan.startup_order.index("b")
        assert plan.extension_plan.shutdown_order.index("b") < \
            plan.extension_plan.shutdown_order.index("a")

    def test_duplicate_extension_fails(self) -> None:
        app = LingShu()
        app.add_extension("ext")
        app.add_extension("ext")
        with pytest.raises(ConfigurationError) as exc_info:
            app.freeze()
        assert exc_info.value.code == "freeze.duplicate_extension"

    def test_extension_cycle_fails(self) -> None:
        app = LingShu()
        app.add_extension("a", dependencies=("b",))
        app.add_extension("b", dependencies=("a",))
        with pytest.raises(ConfigurationError) as exc_info:
            app.freeze()
        assert exc_info.value.code == "freeze.extension_cycle"

    def test_extension_unknown_dependency_fails(self) -> None:
        app = LingShu()
        app.add_extension("a", dependencies=("missing",))
        with pytest.raises(ConfigurationError) as exc_info:
            app.freeze()
        assert exc_info.value.code == "freeze.extension_unknown_dependency"


# --------------------------------------------------------------------------
# Handler return normalization (exactly once)
# --------------------------------------------------------------------------


class TestNormalizeResponse:
    def test_response_normalizes_once(self) -> None:
        from lingshu import normalize_response

        response = Response.text("hello")
        normalized = normalize_response(response)
        assert normalized is response

    def test_str_normalizes(self) -> None:
        from lingshu import normalize_response

        normalized = normalize_response("hello")
        assert normalized.body == b"hello"

    def test_bytes_normalizes(self) -> None:
        from lingshu import normalize_response

        normalized = normalize_response(b"data")
        assert normalized.body == b"data"

    def test_none_rejected(self) -> None:
        from lingshu import normalize_response
        from lingshu.core.errors import HandlerContractError

        with pytest.raises(HandlerContractError):
            normalize_response(None)

    def test_unsupported_rejected(self) -> None:
        from lingshu import normalize_response
        from lingshu.core.errors import HandlerContractError

        with pytest.raises(HandlerContractError):
            normalize_response(123)  # type: ignore[arg-type]

    def test_double_normalization_rejected(self) -> None:
        from lingshu import normalize_response
        from lingshu.core.errors import HandlerContractError

        response = Response.text("hello")
        normalize_response(response)
        with pytest.raises(HandlerContractError):
            normalize_response(response)


# --------------------------------------------------------------------------
# HTTPException
# --------------------------------------------------------------------------


class TestHTTPException:
    def test_basic_http_exception(self) -> None:
        exc = HTTPException(404, "Not found")
        assert exc.status_code == 404
        assert exc.http_status == 404
        assert exc.client_visible
        assert exc.code == "http.status_404"

    def test_http_exception_with_custom_code(self) -> None:
        exc = HTTPException(422, "Invalid", code="custom.validation_error")
        assert exc.code == "custom.validation_error"
        assert exc.http_status == 422

    def test_http_exception_invalid_status_rejected(self) -> None:
        with pytest.raises(ValueError):
            HTTPException(200)

    def test_http_exception_with_headers(self) -> None:
        exc = HTTPException(401, headers={"WWW-Authenticate": "Bearer"})
        assert exc.headers is not None
        assert exc.headers["WWW-Authenticate"] == "Bearer"

    def test_http_exception_default_detail(self) -> None:
        exc = HTTPException(404)
        assert "404" in exc.safe_message or "not" in exc.safe_message.lower()

    def test_http_exception_is_lingshu_error(self) -> None:
        exc = HTTPException(500)
        assert isinstance(exc, LingShuError)


# --------------------------------------------------------------------------
# ApplicationRevision canonical bytes
# --------------------------------------------------------------------------


class TestApplicationRevision:
    def test_revision_canonical_bytes_are_deterministic(self) -> None:
        app1 = LingShu()

        @app1.get("/")
        async def h1(request: Request) -> Response:
            return Response.text("ok")

        rev1 = app1.kernel._catalog.revision()  # type: ignore[attr-defined]
        rev2 = app1.kernel._catalog.revision()  # type: ignore[attr-defined]
        assert rev1.canonical_bytes() == rev2.canonical_bytes()
        assert rev1.revision_id() == rev2.revision_id()

    def test_revision_id_is_sha256_hex(self) -> None:
        app = LingShu()
        plan = app.freeze()
        rid = plan.revision_id
        assert isinstance(rid, RevisionId)
        assert len(rid.value) == 64
        assert all(c in "0123456789abcdef" for c in rid.value)


# --------------------------------------------------------------------------
# No import-time side effects
# --------------------------------------------------------------------------


class TestImportSafety:
    def test_lingshu_construction_has_no_side_effects(self) -> None:
        import os
        import threading

        before_env = dict(os.environ)
        before_threads = {t.ident for t in threading.enumerate()}
        _ = LingShu()
        assert dict(os.environ) == before_env
        assert {t.ident for t in threading.enumerate()} == before_threads

    def test_kernel_exposed_for_integration(self) -> None:
        app = LingShu()
        assert isinstance(app.kernel, Application)


# --------------------------------------------------------------------------
# Application Kernel direct usage
# --------------------------------------------------------------------------


class TestApplicationKernel:
    def test_kernel_freeze_directly(self) -> None:
        kernel = Application()
        plan = kernel.freeze()
        assert kernel.state is ApplicationState.FROZEN
        assert plan is not None

    def test_kernel_rejects_registration_after_freeze(self) -> None:
        kernel = Application()
        kernel.freeze()

        async def handler(request: Request) -> Response:
            return Response.text("ok")

        from lingshu.http.router import RouteDeclaration

        decl = RouteDeclaration("/", ("GET",), handler)
        with pytest.raises(LifecycleError):
            kernel.add_route(decl)
