"""Bounded single-consumer request body primitives."""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator

from lingshu.core.errors import FatalScope, RequestError, ResourceLimitError
from lingshu.runtime import Scope, ScopeState


class RequestBody:
    """One request-owned, bounded, single-consumer body stream."""

    __slots__ = ("_consumed", "_max_bytes", "_scope", "_source")

    def __init__(
        self,
        source: AsyncIterable[bytes],
        *,
        scope: Scope,
        max_bytes: int,
    ) -> None:
        if max_bytes < 0:
            raise ValueError("request body limit must be non-negative")
        self._source = source
        self._scope = scope
        self._max_bytes = max_bytes
        self._consumed = False

    @classmethod
    def from_bytes(cls, value: bytes, *, scope: Scope, max_bytes: int) -> RequestBody:
        """Create a body from already-buffered protocol bytes."""

        async def source() -> AsyncIterator[bytes]:
            if value:
                yield value

        return cls(source(), scope=scope, max_bytes=max_bytes)

    @property
    def consumed(self) -> bool:
        return self._consumed

    async def read(self, *, max_bytes: int | None = None) -> bytes:
        """Buffer the entire body within the configured and caller limits."""

        limit = self._effective_limit(max_bytes)
        chunks = [chunk async for chunk in self._consume(limit)]
        return b"".join(chunks)

    def iter_chunks(self) -> AsyncIterator[bytes]:
        """Consume body chunks exactly once without exposing an unbounded buffer."""

        return self._consume(self._max_bytes)

    def _consume(self, limit: int) -> AsyncIterator[bytes]:
        if self._consumed:
            raise RequestError(
                "request.body_already_consumed",
                "The request body has already been consumed.",
                fatal_scope=FatalScope.REQUEST,
            )
        self._ensure_active()
        self._consumed = True

        async def iterator() -> AsyncIterator[bytes]:
            total = 0
            async for raw_chunk in self._source:
                self._ensure_active()
                if not isinstance(raw_chunk, bytes | bytearray | memoryview):
                    raise RequestError(
                        "request.invalid_body_chunk",
                        "The request body source produced an invalid chunk.",
                        fatal_scope=FatalScope.REQUEST,
                    )
                chunk = bytes(raw_chunk)
                total += len(chunk)
                if total > limit:
                    raise ResourceLimitError(
                        "request.body_too_large",
                        "The request body exceeds the configured limit.",
                        fatal_scope=FatalScope.REQUEST,
                        safe_details={"limit": limit},
                    )
                if chunk:
                    yield chunk
            self._ensure_active()

        return iterator()

    def _effective_limit(self, requested: int | None) -> int:
        if requested is None:
            return self._max_bytes
        if requested < 0:
            raise ValueError("request body read limit must be non-negative")
        return min(self._max_bytes, requested)

    def _ensure_active(self) -> None:
        if self._scope.state is ScopeState.CLOSED:
            raise RequestError(
                "request.scope_closed",
                "The request Scope is closed.",
                fatal_scope=FatalScope.REQUEST,
            )
        self._scope.checkpoint()


__all__ = ("RequestBody",)
