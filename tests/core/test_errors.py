from __future__ import annotations

import asyncio
import math
from collections.abc import Mapping

import pytest
from lingshu.core import (
    FatalScope,
    LingShuError,
    RequestError,
    RequestId,
    Severity,
    freeze_safe_details,
    problem_from_exception,
    validate_error_code,
)


def test_error_code_validation() -> None:
    assert validate_error_code("request.body_too_large") == "request.body_too_large"
    for invalid in ("request", "Request.invalid", "request-invalid", ".request.invalid", "a..b"):
        with pytest.raises(ValueError):
            validate_error_code(invalid)


def test_safe_details_are_recursive_and_immutable() -> None:
    original = {"limit": 10, "nested": {"allowed": True}, "items": ["a", "b"]}
    frozen = freeze_safe_details(original)
    original["limit"] = 99
    assert frozen["limit"] == 10
    assert frozen["items"] == ("a", "b")
    nested = frozen["nested"]
    assert isinstance(nested, Mapping)
    with pytest.raises(TypeError):
        nested["allowed"] = False  # type: ignore[index]
    with pytest.raises(TypeError):
        frozen["new"] = "value"  # type: ignore[index]


def test_safe_details_reject_unsafe_values() -> None:
    for value in (object(), b"secret", math.inf, -math.inf, math.nan):
        with pytest.raises((TypeError, ValueError)):
            freeze_safe_details({"value": value})
    with pytest.raises(TypeError):
        freeze_safe_details({1: "value"})  # type: ignore[dict-item]


def test_client_visible_problem_contains_only_safe_fields() -> None:
    cause = RuntimeError("password=hunter2 /private/source.py")
    error = RequestError(
        "request.body_too_large",
        "The request body exceeds the configured limit.",
        title="Request body too large",
        client_visible=True,
        retryable=False,
        http_status=413,
        severity=Severity.WARNING,
        fatal_scope=FatalScope.REQUEST,
        safe_details={"limit": 1024, "units": "bytes"},
        cause=cause,
    )
    request_id = RequestId.parse("a" * 32)

    document = problem_from_exception(error, request_id=request_id).to_dict()

    assert document == {
        "type": "urn:lingshu:error:request.body_too_large",
        "title": "Request body too large",
        "status": 413,
        "detail": "The request body exceeds the configured limit.",
        "code": "request.body_too_large",
        "instance": f"urn:lingshu:request:{request_id}",
        "request_id": str(request_id),
        "details": {"limit": 1024, "units": "bytes"},
    }
    serialized = repr(document)
    assert "hunter2" not in serialized
    assert "/private/source.py" not in serialized
    assert "cause" not in document
    assert "traceback" not in document


def test_hidden_framework_error_maps_to_generic_internal_problem() -> None:
    error = LingShuError(
        "storage.secret_failure",
        "Database password was exposed at /private/path.",
        cause=RuntimeError("token=secret"),
    )
    document = problem_from_exception(error).to_dict()
    assert document == {
        "type": "urn:lingshu:error:internal.error",
        "title": "Internal Server Error",
        "status": 500,
        "detail": "An internal error occurred.",
        "code": "internal.error",
    }
    assert "secret" not in repr(document)
    assert "/private/path" not in repr(document)


def test_unexpected_exception_maps_to_generic_internal_problem() -> None:
    document = problem_from_exception(ValueError("api_key=secret")).to_dict()
    assert document["code"] == "internal.error"
    assert "secret" not in repr(document)


def test_client_visible_error_requires_valid_http_status() -> None:
    with pytest.raises(ValueError, match="require an HTTP status"):
        RequestError("request.invalid", "Invalid request.", client_visible=True)
    with pytest.raises(ValueError, match="between 400 and 599"):
        RequestError("request.invalid", "Invalid request.", http_status=200)


def test_control_flow_base_exception_is_not_mapped() -> None:
    cancellation = asyncio.CancelledError()
    with pytest.raises(TypeError, match="control-flow"):
        problem_from_exception(cancellation)
