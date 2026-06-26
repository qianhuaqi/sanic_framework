from __future__ import annotations

import asyncio
from uuid import uuid4

from lingshu.system.context import bind_request_context
from lingshu.system.execution import RequestExecutionContext, bind_execution_context
from lingshu.system.errors import ResourceNotConfiguredError
from lingshu.system.policy import CompiledRoutePolicy, RoutePolicyError


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


def get_request_execution_context(raw_request):
    ctx = getattr(raw_request, "ctx", None)
    return getattr(ctx, "lingshu_execution_context", None)


def _exit_execution_context(raw_request):
    ctx = getattr(raw_request, "ctx", None)
    if ctx is None:
        return
    token = getattr(ctx, "lingshu_execution_token", None)
    if token is not None:
        token.reset()
        setattr(ctx, "lingshu_execution_token", None)


def reset_request_context(raw_request):
    _exit_execution_context(raw_request)
    context = get_request_context(raw_request)
    if context is not None:
        context.reset()
    ctx = getattr(raw_request, "ctx", None)
    if ctx is not None:
        setattr(ctx, "lingshu_context", None)
        setattr(ctx, "lingshu_execution_context", None)


def detach_request_context_after_task(raw_request):
    context = get_request_context(raw_request)
    ctx = getattr(raw_request, "ctx", None)
    if context is None:
        if ctx is not None:
            token = getattr(ctx, "lingshu_execution_token", None)
            if token is not None:
                token.detach_after_task()
            setattr(ctx, "lingshu_execution_context", None)
            setattr(ctx, "lingshu_execution_token", None)
        return
    # A done callback may run after cancellation/disconnect, when the owning
    # asyncio task context is gone. Do not reset ContextVar tokens there;
    # just detach request references so the completed task does not retain them.
    context.detach_after_task()
    if ctx is not None:
        token = getattr(ctx, "lingshu_execution_token", None)
        if token is not None:
            token.detach_after_task()
        setattr(ctx, "lingshu_context", None)
        setattr(ctx, "lingshu_execution_context", None)
        setattr(ctx, "lingshu_execution_token", None)


def _request_route_name(raw_app, request):
    route = getattr(request, "route", None)
    if route is None:
        return ""
    route_name = getattr(route, "name", "") or getattr(getattr(route, "handler", None), "__name__", "")
    prefix = f"{raw_app.name}."
    if route_name.startswith(prefix):
        return route_name[len(prefix) :]
    return route_name


def _route_policy_for_request(raw_app, request) -> CompiledRoutePolicy:
    route_name = _request_route_name(raw_app, request)
    compiled = getattr(raw_app.ctx, "route_policies", None)
    if compiled is not None and route_name:
        try:
            return compiled.for_route(route_name)
        except RoutePolicyError:
            pass
    return CompiledRoutePolicy(
        route_name=route_name or "unknown",
        public=False,
        auth_required=True,
        maintenance_check=True,
        timeout=10.0,
        body_limit=None,
        audit_level="none",
    )


def _lifecycle_state(raw_app) -> str:
    lifecycle = getattr(raw_app.ctx, "lifecycle", None)
    state = getattr(lifecycle, "state", None)
    return getattr(state, "value", "ready")


def install_context_middleware(raw_app):
    @raw_app.middleware("request")
    async def bind_lingshu_context(request):
        route_policy = _route_policy_for_request(raw_app, request)
        execution_context = RequestExecutionContext.child(
            request_id=get_request_id(request),
            trace_id=request.headers.get("traceparent") or request.headers.get("X-Trace-ID") or uuid4().hex,
            operation_id=request.headers.get("X-Operation-ID"),
            route_policy=route_policy,
            timeout=route_policy.timeout,
            lifecycle_state=_lifecycle_state(raw_app),
        )
        context = bind_request_context(
            raw_app,
            request,
            request_id=execution_context.request_id,
            user=get_request_user(request),
        )
        request.ctx.lingshu_context = context
        request.ctx.lingshu_execution_context = execution_context
        request.ctx.lingshu_execution_token = bind_execution_context(execution_context)
        request.ctx.lingshu_execution_token.__enter__()
        task = asyncio.current_task()
        if task is not None:
            # Covers cancellation/disconnect paths that do not produce a response
            # and may bypass Sanic's ordinary exception lifecycle.
            task.add_done_callback(
                lambda _task, raw_request=request: detach_request_context_after_task(raw_request),
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
