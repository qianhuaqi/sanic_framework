from __future__ import annotations

from lingshu.system.context import request_context
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
    return getattr(ctx, "request_id", None) or raw_request.headers.get("X-Request-ID", "")


def install_context_middleware(raw_app):
    @raw_app.middleware("request")
    async def bind_lingshu_context(request):
        request.ctx.lingshu_context = request_context(raw_app, request, request_id=get_request_id(request), user=get_request_user(request))
        request.ctx.lingshu_context.__enter__()

    @raw_app.middleware("response")
    async def reset_lingshu_context(request, response):
        context = getattr(request.ctx, "lingshu_context", None)
        if context is not None:
            context.__exit__(None, None, None)
            request.ctx.lingshu_context = None
