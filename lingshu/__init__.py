"""LingShu public application facade.

Importing this package has no runtime side effects: it does not start tasks, open files,
bind sockets, connect to services, or import user applications.
"""

from lingshu.core.application import HTTPException, LingShu, normalize_handler_return
from lingshu.http.request import Request
from lingshu.http.response import Response, SupportedReturnValue, normalize_response

__all__ = (
    "HTTPException",
    "LingShu",
    "Request",
    "Response",
    "SupportedReturnValue",
    "normalize_handler_return",
    "normalize_response",
)
