from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from lingshu.core import ConnectionId, RequestId
from lingshu.http import (
    Headers,
    HTTPMethod,
    HTTPVersion,
    Request,
    RequestBody,
    RequestTarget,
)
from lingshu.runtime import CancellationReason, Scope, ScopeCancelled, ScopeKind


def make_request(
    body_value: bytes = b"hello", *, max_bytes: int = 16
) -> tuple[Scope, Scope, Request]:
    application = Scope.application()
    connection = application.create_child(ScopeKind.CONNECTION)
    request_scope = connection.create_child(ScopeKind.REQUEST, duration_ns=5_000_000_000)
    body = RequestBody.from_bytes(body_value, scope=request_scope, max_bytes=max_bytes)
    request = Request(
        method=HTTPMethod("get"),
        target=RequestTarget.parse("/users/42?active=1"),
        version=HTTPVersion.HTTP_1_1,
        headers=Headers((("host", "example.test"),)),
        scope=request_scope,
        body=body,
        request_id=RequestId.parse("a" * 32),
        connection_id=ConnectionId.parse("b" * 32),
        authority="example.test",
    )
    return application, request_scope, request


def test_body_is_single_consumer_and_bounded() -> None:
    async def scenario() -> None:
        application, _, request = make_request()
        assert await request.body.read() == b"hello"
        with pytest.raises(Exception) as consumed:
            await request.body.read()
        assert consumed.value.code == "request.body_already_consumed"
        await application.close()

        application, _, request = make_request(b"too-large", max_bytes=4)
        with pytest.raises(Exception) as limited:
            await request.body.read()
        assert limited.value.code == "request.body_too_large"
        await application.close()

    asyncio.run(scenario())


def test_body_chunk_iteration_preserves_order_and_single_use() -> None:
    async def scenario() -> None:
        application = Scope.application()
        connection = application.create_child(ScopeKind.CONNECTION)
        request_scope = connection.create_child(ScopeKind.REQUEST, duration_ns=5_000_000_000)

        async def source() -> AsyncIterator[bytes]:
            yield b"one"
            yield b"two"

        body = RequestBody(source(), scope=request_scope, max_bytes=6)
        assert [chunk async for chunk in body.iter_chunks()] == [b"one", b"two"]
        with pytest.raises(Exception) as consumed:
            body.iter_chunks()
        assert consumed.value.code == "request.body_already_consumed"
        await application.close()

    asyncio.run(scenario())


def test_request_metadata_route_state_and_scope_lifetime() -> None:
    async def scenario() -> None:
        application, _, request = make_request()
        assert str(request.method) == "GET"
        assert request.path == "/users/42"
        assert request.query == "active=1"
        request.state["user"] = 42
        request.publish_route("user-detail", {"user_id": "42"})
        assert request.route_name == "user-detail"
        assert request.path_params == {"user_id": "42"}
        with pytest.raises(TypeError):
            request.path_params["user_id"] = "43"  # type: ignore[index]
        with pytest.raises(Exception) as duplicate:
            request.publish_route("again", {})
        assert duplicate.value.code == "request.route_already_published"

        await application.close()
        with pytest.raises(Exception) as closed:
            _ = request.path
        assert closed.value.code == "request.scope_closed"

    asyncio.run(scenario())


def test_scope_cancellation_remains_control_flow() -> None:
    async def scenario() -> None:
        application, request_scope, request = make_request()
        request_scope.cancel(CancellationReason.CLIENT_DISCONNECT)
        caught_by_exception = False
        try:
            await request.body.read()
        except Exception:
            caught_by_exception = True
        except ScopeCancelled:
            pass
        assert not caught_by_exception
        await application.close()

    asyncio.run(scenario())
