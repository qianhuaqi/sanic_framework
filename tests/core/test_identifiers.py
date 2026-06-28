from __future__ import annotations

import hashlib

import pytest
from lingshu.core import (
    ConnectionId,
    FatalScope,
    InternalError,
    RequestId,
    RevisionId,
    Severity,
    validate_external_request_id,
)


def test_generated_ids_are_unique_canonical_and_immutable() -> None:
    values = {RequestId.generate() for _ in range(512)}
    assert len(values) == 512
    for identifier in values:
        assert len(str(identifier)) == 32
        assert str(identifier) == str(identifier).lower()
        int(str(identifier), 16)
    with pytest.raises(AttributeError):
        next(iter(values)).value = "0" * 32  # type: ignore[misc]


def test_identifier_types_are_not_interchangeable() -> None:
    value = "a" * 32
    request_id = RequestId.parse(value)
    connection_id = ConnectionId.parse(value)
    assert request_id != connection_id
    assert type(request_id) is RequestId
    assert type(connection_id) is ConnectionId


def test_identifier_parser_rejects_noncanonical_text() -> None:
    for invalid in ("A" * 32, "a" * 31, "a" * 33, "a" * 16 + "-" + "a" * 15):
        with pytest.raises(ValueError):
            RequestId.parse(invalid)


def test_entropy_failure_becomes_safe_internal_error() -> None:
    cause = OSError("secret filesystem path /private/key")

    def fail(_: int) -> bytes:
        raise cause

    with pytest.raises(InternalError) as captured:
        RequestId.generate(fail)

    error = captured.value
    assert error.code == "internal.identifier_generation_failed"
    assert error.safe_message == "Unable to generate an internal identifier."
    assert error.client_visible is False
    assert error.severity is Severity.CRITICAL
    assert error.fatal_scope is FatalScope.OPERATION
    assert error.internal_cause is cause
    assert "/private/key" not in str(error)


@pytest.mark.parametrize("value", [b"short", b"long" * 8])
def test_entropy_source_must_return_exact_bytes(value: bytes) -> None:
    def source(_: int) -> bytes:
        return value

    with pytest.raises(InternalError):
        RequestId.generate(source)


def test_revision_id_is_deterministic_sha256() -> None:
    canonical = b'{"routes":[],"version":1}'
    revision = RevisionId.from_canonical_bytes(canonical)
    assert str(revision) == hashlib.sha256(canonical).hexdigest()
    assert RevisionId.parse(str(revision)) == revision


def test_external_request_id_validation_is_bounded_and_untrusted() -> None:
    assert validate_external_request_id("client-123.example:trace") == "client-123.example:trace"
    for invalid in ("", "has space", "line\nbreak", "slash/value", "x" * 129):
        with pytest.raises(ValueError):
            validate_external_request_id(invalid)
    with pytest.raises(ValueError):
        validate_external_request_id("ok", max_length=0)
