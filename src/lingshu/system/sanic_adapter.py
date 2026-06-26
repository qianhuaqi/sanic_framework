from __future__ import annotations

import asyncio
import contextvars
from uuid import uuid4

from lingshu.system.context import bind_request_context
from lingshu.system.errors import ResourceNotConfiguredError


def set_app_config(raw_app, config):
    raw_app.ctx.config = config


def get_app_config(raw_app):
    return raw_app.ctx.config


def set_app_logger(raw_app, logger):
    raw_app.ctx.logger = logger


def get_app_logger(raw_app):
    return raw_app.ctx.logger


def set_resource(raw_app, name: str, value):
    setattr(raw_app.ctx, name, value)


def get_resource(raw_app, name: str):
    value = getattr(raw_app.ctx, name, None)
    if value is None:
        raise ResourceNotConfiguredError(f"Resource '{name}' is not configured")
    return value


def get_optional_resource(raw_app, name: str):
    return getattr(raw_app.ctx, name, None)


def get_request_app(raw_request):
    return raw_request.app


def get_request_config(raw_request):
    return get_app_config(get_request_app(raw_request))


def get_request_resource(raw_request, name: str):
    return get_resource(get_request_app(raw_request), name)


def get_optional_request_resource(raw_request, name: str):
    return get_optional_resource(get_request_app(raw_request), name)


def get_request_user(raw_request):
    ctx = getattr(raw_request, "ctx", None)
    return getattr(ctx, "g", None)


def get_request_id(raw_request):
    ctx = getattr(raw_request, "ctx", None)
    request_id = getattr(ctx, "request_id", None)
    if request_id:
        return request_id
    headers = getattr(raw_request, "headers", {}) or {}
    request_id = headers.get("X-Request-ID") or headers.get("x-request-id")
    return request_id or uuid4().hex


def get_request_context(raw_request):
    ctx = getattr(raw_request, "ctx", None)
    return getattr(ctx, "lingshu_context", None)


def reset_request_context(raw_request):
    context = get_request_context(raw_request)
    if context is None:
        return
    context.reset()
    ctx = getattr(raw_request, "ctx", None)
    if ctx is not None:
        setattr(ctx, "lingshu_context", None)


def install_context_middleware(raw_app):
    @raw_app.middleware("request")
    async def bind_lingshu_context(request):
        context = bind_request_context(
            raw_app,
            request,
            request_id=get_request_id(request),
            user=get_request_user(request),
        )
        request.ctx.lingshu_context = context
        task = asyncio.current_task()
        if task is not None:
            # Covers cancellation/disconnect paths that do not produce a response
            # and may bypass Sanic's ordinary exception lifecycle.
            task.add_done_callback(
                lambda _task, raw_request=request: reset_request_context(raw_request),
                context=contextvars.copy_context(),
            )

    @raw_app.middleware("response")
    async def reset_lingshu_context(request, response):
        reset_request_context(request)

    @raw_app.signal("http.lifecycle.response")
    async def reset_lingshu_context_after_response(request, response, **_):
        reset_request_context(request)

    @raw_app.signal("http.lifecycle.exception")
    async def reset_lingshu_context_after_exception(request, exception, **_):
        if request is not None:
            reset_request_context(request)
