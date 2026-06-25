from __future__ import annotations


class LingShuError(RuntimeError):
    """Base error for LingShu Framework."""


class LingShuContextError(LingShuError):
    """Base error for missing LingShu runtime context."""


class NoAppContextError(LingShuContextError):
    """Raised when an app-bound facade is used without an app context."""


class NoRequestContextError(LingShuContextError):
    """Raised when a request-bound facade is used without a request context."""


class ResourceNotConfiguredError(LingShuError):
    """Raised when an app resource is not configured."""

