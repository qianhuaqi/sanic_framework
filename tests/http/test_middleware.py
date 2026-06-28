from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError

import pytest
from lingshu.core import ConnectionId, HandlerContractError, LifecycleError, RequestId
from lingshu.http import (
    Headers,
    HTTPMethod,
    HTTPVersion,
    MiddlewareCallable,
    MiddlewareDeclaration,
    MiddlewareScope,
    Next,
    Request,
    RequestBody,
    RequestTarget,
    Response,
    compile_middleware,
)
from lingshu.runtime import CancellationReason, Scope, ScopeCancelled, ScopeKind


def make_request() -> tuple[Scope, Scope, Request]:
    application = Scope.application()
    connection = application.create_child(ScopeKind.CONNECTION)
    request_scope = connection.create_child(
        ScopeKind.REQUEST,
        duration_ns=5_000_000_000,
    )
    request = Request(
        method=HTTPMethod("GET"),
        target=RequestTarget.parse("/middleware"),
        version=HTTPVersion.HTTP_1_1,
        headers=Headers((("host", "example.test"),)),
        scope=request_scope,
        body=RequestBody.from_bytes(b"", scope=request_scope, max_bytes=0),
        request_id=RequestId.parse("a" * 32),
        connection_id=ConnectionId.parse("b" * 32),
    )
    return application, request_scope, request


def wrapping_middleware(
    label: str,
    events: list[str],
) -> MiddlewareCallable:
    async def callback(request: Request, call_next: Next) -> Response:
        del request
        events.append(f"{label}:in")
        response = await call_next()
        events.append(f"{label}:out")
        return response

    return callback


def test_application_and_route_middleware_follow_deterministic_onion_order() -> None:
    async def scenario() -> None:
        application, _, request = make_request()
        events: list[str] = []
        app_plan = compile_middleware(
            MiddlewareScope.APPLICATION,
            (
                MiddlewareDeclaration(wrapping_middleware("B", events), priority=10),
                MiddlewareDeclaration(wrapping_middleware("A", events), priority=0),
                MiddlewareDeclaration(wrapping_middleware("C", events), priority=10),
            ),
        )
        route_plan = compile_middleware(
            MiddlewareScope.ROUTE,
            (
                MiddlewareDeclaration(wrapping_middleware("Y", events), priority=1),
                MiddlewareDeclaration(wrapping_middleware("X", events), priority=0),
            ),
        )

        async def terminal(request: Request) -> Response:
            del request
            events.append("handler")
            return Response.text("ok")

        try:
            response = await app_plan.run(
                request,
                lambda current: route_plan.run(current, terminal),
            )
            assert response.body == b"ok"
            assert events == [
                "A:in",
                "B:in",
                "C:in",
                "X:in",
                "Y:in",
                "handler",
                "Y:out",
                "X:out",
                "C:out",
                "B:out",
                "A:out",
            ]
            with pytest.raises(FrozenInstanceError):
                setattr(app_plan, "scope", MiddlewareScope.ROUTE)
        finally:
            await application.close()

    asyncio.run(scenario())


def test_short_circuit_skips_downstream_execution() -> None:
    async def scenario() -> None:
        application, _, request = make_request()
        called = False

        async def short_circuit(request: Request, call_next: Next) -> Response:
            del request, call_next
            return Response.text("short")

        async def terminal(request: Request) -> Response:
            nonlocal called
            del request
            called = True
            return Response.text("unexpected")

        try:
            plan = compile_middleware(
                MiddlewareScope.APPLICATION,
                (MiddlewareDeclaration(short_circuit),),
            )
            assert (await plan.run(request, terminal)).body == b"short"
            assert not called
        finally:
            await application.close()

    asyncio.run(scenario())


def test_call_next_is_single_use_task_bound_and_not_delayed() -> None:
    async def scenario() -> None:
        application, _, request = make_request()

        async def terminal(request: Request) -> Response:
            del request
            return Response.text("ok")

        async def double_call(request: Request, call_next: Next) -> Response:
            del request
            await call_next()
            return await call_next()

        try:
            plan = compile_middleware(
                MiddlewareScope.APPLICATION,
                (MiddlewareDeclaration(double_call),),
            )
            with pytest.raises(LifecycleError) as reused:
                await plan.run(request, terminal)
            assert reused.value.code == "middleware.call_next_reused"
        finally:
            await application.close()

        application, _, request = make_request()
        saved: list[Next] = []

        async def save_for_later(request: Request, call_next: Next) -> Response:
            del request
            saved.append(call_next)
            return Response.text("done")

        try:
            plan = compile_middleware(
                MiddlewareScope.APPLICATION,
                (MiddlewareDeclaration(save_for_later),),
            )
            await plan.run(request, terminal)
            with pytest.raises(LifecycleError) as inactive:
                saved[0]()
            assert inactive.value.code == "middleware.call_next_inactive"
        finally:
            await application.close()

        application, _, request = make_request()

        async def cross_task(request: Request, call_next: Next) -> Response:
            del request

            async def invoke() -> Response:
                return await call_next()

            return await asyncio.create_task(invoke())

        try:
            plan = compile_middleware(
                MiddlewareScope.APPLICATION,
                (MiddlewareDeclaration(cross_task),),
            )
            with pytest.raises(LifecycleError) as wrong_task:
                await plan.run(request, terminal)
            assert wrong_task.value.code == "middleware.call_next_wrong_task"
        finally:
            await application.close()

    asyncio.run(scenario())


def test_middleware_contract_rejects_sync_and_non_response_results() -> None:
    def synchronous(request: Request, call_next: Next) -> Response:
        del request, call_next
        return Response.text("invalid")

    with pytest.raises(HandlerContractError) as sync_error:
        compile_middleware(
            MiddlewareScope.APPLICATION,
            (MiddlewareDeclaration(synchronous),),  # type: ignore[arg-type]
        )
    assert sync_error.value.code == "middleware.async_required"

    async def scenario() -> None:
        application, _, request = make_request()

        async def invalid(request: Request, call_next: Next) -> Response:
            del request, call_next
            return "invalid"  # type: ignore[return-value]

        async def terminal(request: Request) -> Response:
            del request
            return Response.text("ok")

        try:
            plan = compile_middleware(
                MiddlewareScope.APPLICATION,
                (MiddlewareDeclaration(invalid),),
            )
            with pytest.raises(HandlerContractError) as invalid_return:
                await plan.run(request, terminal)
            assert invalid_return.value.code == "middleware.invalid_return"
        finally:
            await application.close()

    asyncio.run(scenario())


def test_scope_cancellation_remains_base_exception_control_flow() -> None:
    async def scenario() -> None:
        application, request_scope, request = make_request()
        caught_as_exception = False

        async def guard(request: Request, call_next: Next) -> Response:
            nonlocal caught_as_exception
            del request
            try:
                return await call_next()
            except Exception:
                caught_as_exception = True
                return Response.text("caught")

        async def terminal(request: Request) -> Response:
            del request
            request_scope.cancel(CancellationReason.CLIENT_DISCONNECT)
            request_scope.checkpoint()
            raise AssertionError("unreachable")

        try:
            plan = compile_middleware(
                MiddlewareScope.APPLICATION,
                (MiddlewareDeclaration(guard),),
            )
            with pytest.raises(ScopeCancelled):
                await plan.run(request, terminal)
            assert not caught_as_exception
        finally:
            await application.close()

    asyncio.run(scenario())


def test_closed_request_scope_rejects_middleware_execution() -> None:
    async def scenario() -> None:
        application, _, request = make_request()
        await application.close()

        async def terminal(request: Request) -> Response:
            del request
            return Response.text("unexpected")

        plan = compile_middleware(MiddlewareScope.APPLICATION, ())
        with pytest.raises(LifecycleError) as inactive:
            await plan.run(request, terminal)
        assert inactive.value.code == "middleware.scope_inactive"

    asyncio.run(scenario())
