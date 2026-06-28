from __future__ import annotations

import pytest
from lingshu.core import LifecycleError
from lingshu.http import Response, ResponseState, normalize_response


def test_response_factories_prepare_commit_and_complete() -> None:
    response = Response.text("hello")
    assert response.state is ResponseState.NEW
    assert response.headers.get("content-type") == "text/plain; charset=utf-8"

    head = response.prepare()
    assert response.state is ResponseState.PREPARED
    assert head.headers.get("content-length") == "5"

    response.write(b"!")
    assert response.state is ResponseState.NEW
    head = response.commit()
    assert head.headers.get("content-length") == "6"
    assert response.state is ResponseState.COMMITTED

    with pytest.raises(LifecycleError) as duplicate:
        response.commit()
    assert duplicate.value.code == "response.invalid_state"
    with pytest.raises(LifecycleError):
        response.set_header("x-test", "value")
    response.complete()
    assert response.state is ResponseState.COMPLETED
    with pytest.raises(LifecycleError):
        response.abort()


def test_abort_is_terminal_and_idempotent() -> None:
    response = Response.bytes(b"payload", status=202)
    assert response.abort()
    assert not response.abort()
    assert response.state is ResponseState.ABORTED
    with pytest.raises(LifecycleError):
        response.write(b"later")


def test_return_normalization_is_exactly_once() -> None:
    assert normalize_response("hello").body == b"hello"
    assert normalize_response(bytearray(b"bytes")).body == b"bytes"
    assert normalize_response(memoryview(b"view")).body == b"view"

    response = Response.bytes(b"ok")
    assert normalize_response(response) is response
    with pytest.raises(Exception) as duplicate:
        normalize_response(response)
    assert duplicate.value.code == "handler.return_already_normalized"


@pytest.mark.parametrize("value", [None, ("body", 200), iter([b"body"]), object()])
def test_invalid_return_values_fail_explicitly(value: object) -> None:
    with pytest.raises(Exception) as captured:
        normalize_response(value)
    assert captured.value.code == "handler.invalid_return"
