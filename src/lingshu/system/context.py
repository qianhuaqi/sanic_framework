from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar

from lingshu.system.errors import NoAppContextError, NoRequestContextError


current_app: ContextVar[object | None] = ContextVar("lingshu_current_app", default=None)
current_request: ContextVar[object | None] = ContextVar("lingshu_current_request", default=None)
current_request_id: ContextVar[str | None] = ContextVar("lingshu_current_request_id", default=None)
current_user: ContextVar[object | None] = ContextVar("lingshu_current_user", default=None)


def get_current_app():
    raw_app = current_app.get()
    if raw_app is None:
        raise NoAppContextError("No LingShu app context is active")
    return raw_app


def get_current_request():
    raw_request = current_request.get()
    if raw_request is None:
        raise NoRequestContextError("No LingShu request context is active")
    return raw_request


@contextmanager
def app_context(raw_app):
    token = current_app.set(raw_app)
    try:
        yield raw_app
    finally:
        current_app.reset(token)


@asynccontextmanager
async def async_app_context(raw_app):
    with app_context(raw_app):
        yield raw_app


@contextmanager
def request_context(raw_app, raw_request, request_id=None, user=None):
    app_token = current_app.set(raw_app)
    request_token = current_request.set(raw_request)
    request_id_token = current_request_id.set(request_id)
    user_token = current_user.set(user)
    try:
        yield raw_request
    finally:
        current_user.reset(user_token)
        current_request_id.reset(request_id_token)
        current_request.reset(request_token)
        current_app.reset(app_token)

