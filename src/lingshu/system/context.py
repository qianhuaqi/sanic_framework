from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from contextvars import ContextVar
from uuid import uuid4

from lingshu.system.errors import NoAppContextError, NoRequestContextError


current_app: ContextVar[object | None] = ContextVar("lingshu_current_app", default=None)
current_request: ContextVar[object | None] = ContextVar("lingshu_current_request", default=None)
current_request_id: ContextVar[str | None] = ContextVar("lingshu_current_request_id", default=None)
current_user: ContextVar[object | None] = ContextVar("lingshu_current_user", default=None)


def _reset_or_clear(variable: ContextVar, token):
    try:
        variable.reset(token)
    except ValueError:
        variable.set(None)


@dataclass
class _ContextTokens:
    app_token: object | None = None
    request_token: object | None = None
    request_id_token: object | None = None
    user_token: object | None = None
    entered: bool = False
    reset_done: bool = False

    def enter(self, raw_app, raw_request, request_id=None, user=None):
        if self.entered:
            return raw_request
        self.app_token = current_app.set(raw_app)
        self.request_token = current_request.set(raw_request)
        self.request_id_token = current_request_id.set(request_id)
        self.user_token = current_user.set(user)
        self.entered = True
        return raw_request

    def reset(self):
        if not self.entered or self.reset_done:
            return
        if self.user_token is not None:
            _reset_or_clear(current_user, self.user_token)
        if self.request_id_token is not None:
            _reset_or_clear(current_request_id, self.request_id_token)
        if self.request_token is not None:
            _reset_or_clear(current_request, self.request_token)
        if self.app_token is not None:
            _reset_or_clear(current_app, self.app_token)
        self.reset_done = True


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
    context = _ContextTokens()
    try:
        if request_id is None:
            request_id = uuid4().hex
        context.enter(raw_app, raw_request, request_id=request_id, user=user)
        yield raw_request
    finally:
        context.reset()


def bind_request_context(raw_app, raw_request, request_id=None, user=None) -> _ContextTokens:
    context = _ContextTokens()
    if request_id is None:
        request_id = uuid4().hex
    context.enter(raw_app, raw_request, request_id=request_id, user=user)
    return context
