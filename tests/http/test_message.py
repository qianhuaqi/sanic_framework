from __future__ import annotations

import pytest
from lingshu.http import Headers, HTTPMethod, HTTPVersion, RequestTarget


def test_method_target_and_version_are_canonical() -> None:
    assert str(HTTPMethod("get")) == "GET"
    assert HTTPVersion("HTTP/1.1") is HTTPVersion.HTTP_1_1
    target = RequestTarget.parse("/hello/world?q=1")
    assert target.raw == "/hello/world?q=1"
    assert target.path == "/hello/world"
    assert target.query == "q=1"


@pytest.mark.parametrize("value", ["", "relative", "/has#fragment", "/nul\x00"])
def test_invalid_request_targets_fail_safely(value: str) -> None:
    with pytest.raises(Exception) as captured:
        RequestTarget.parse(value)
    assert captured.value.code in {"protocol.invalid_target", "request.target_too_large"}


def test_headers_are_immutable_bounded_and_duplicate_preserving() -> None:
    headers = Headers((("Set-Cookie", "a=1"), (b"set-cookie", b"b=2"), ("X-Test", " ok ")))
    assert headers.get_all("SET-cookie") == ("a=1", "b=2")
    assert headers.get("x-test") == "ok"
    assert headers.items()[0] == ("set-cookie", "a=1")
    assert headers.contains("X-TEST")
    assert tuple(headers) == headers.items()

    with pytest.raises(Exception) as too_many:
        Headers((("x-a", "1"), ("x-b", "2")), max_fields=1)
    assert too_many.value.code == "request.headers_too_many"


@pytest.mark.parametrize(
    ("name", "value", "code"),
    [
        ("bad name", "value", "protocol.invalid_header_name"),
        ("x-test", "line\nbreak", "protocol.invalid_header_value"),
    ],
)
def test_invalid_headers_fail_safely(name: str, value: str, code: str) -> None:
    with pytest.raises(Exception) as captured:
        Headers(((name, value),))
    assert captured.value.code == code
