import time
from uuid import uuid4

from sanic import response
from lingshu.system import sanic_adapter


def _join_header(values):
    return ", ".join(str(item).strip() for item in values if str(item).strip())


def _resolve_cors_origin(config, request):
    origin = request.headers.get("origin")
    origins = getattr(config, "cors_origins", ["*"])
    allow_credentials = bool(getattr(config, "cors_allow_credentials", False))
    if "*" in origins:
        return origin if allow_credentials and origin else "*"
    if origin and origin in origins:
        return origin
    return ""


def _build_cors_headers(config, request):
    allowed_origin = _resolve_cors_origin(config, request)
    if not allowed_origin:
        return {}
    headers = {
        "Access-Control-Allow-Origin": allowed_origin,
        "Access-Control-Allow-Methods": _join_header(getattr(config, "cors_allow_methods", [])),
        "Access-Control-Allow-Headers": _join_header(getattr(config, "cors_allow_headers", [])),
        "Access-Control-Max-Age": str(getattr(config, "cors_max_age", 86400)),
        "Vary": "Origin",
    }
    if getattr(config, "cors_allow_credentials", False):
        headers["Access-Control-Allow-Credentials"] = "true"
    return headers


def register_middleware(app):
    @app.middleware("request")
    async def attach_request_context(request):
        request.ctx.request_id = uuid4().hex
        request.ctx.start_time = time.time()
        config = sanic_adapter.get_app_config(request.app)
        if (
            config is not None
            and getattr(config, "cors_enabled", False)
            and request.method.upper() == "OPTIONS"
        ):
            return response.empty(status=204, headers=_build_cors_headers(config, request))

    @app.middleware("response")
    async def attach_request_id(request, response):
        request_id = getattr(request.ctx, "request_id", "")
        response.headers["X-Request-ID"] = request_id
        config = sanic_adapter.get_app_config(request.app)
        if config is not None and getattr(config, "cors_enabled", False):
            response.headers.update(_build_cors_headers(config, request))
