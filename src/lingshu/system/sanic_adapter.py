from __future__ import annotations

import asyncio
from uuid import uuid4

from lingshu.response import json_response
from lingshu.system.context import bind_request_context
from lingshu.system.execution import (
    CancellationReason,
    RequestExecutionContext,
    bind_execution_context,
)
from lingshu.system.errors import ResourceNotConfiguredError
from lingshu.system.policy import CompiledRoutePolicy


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


_REQUEST_TASK_CLEANUP_BUDGET = 2.0
_REQUEST_TASK_CLEANUP_MIN = 0.5


def _cleanup_budget(execution_context) -> float:
    remaining = max(0.0, execution_context.remaining)
    return max(_REQUEST_TASK_CLEANUP_MIN, min(_REQUEST_TASK_CLEANUP_BUDGET, remaining))


async def finalize_request_context(raw_request, *, reason=None):
    """Idempotent, unconditional request finalizer.

    Ensures in-flight tracker release and context reset happen regardless of
    whether task cleanup succeeds, fails, or times out.
    """
    ctx = getattr(raw_request, "ctx", None)
    if ctx is None or getattr(ctx, "lingshu_finalized", False):
        return
    setattr(ctx, "lingshu_finalized", True)

    execution_context = get_request_execution_context(raw_request)

    if execution_context is not None and reason is not None and execution_context.cancel_reason is None:
        execution_context.cancel(reason)

    cleanup_errors = []

    try:
        if execution_context is not None:
            registry = getattr(raw_request.app.ctx, "task_registry", None)
            if registry is not None:
                budget = _cleanup_budget(execution_context)
                await registry.finish_request(execution_context.execution_id, timeout=budget)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        cleanup_errors.append(exc)
        logger = get_optional_resource(raw_request.app, "logger")
        if logger is not None:
            from lingshu.system.tasks import _summarize_exception

            exc_type, safe_msg = _summarize_exception(exc)
            logger.debug("Request task cleanup error: %s: %s", exc_type, safe_msg)
    finally:
        if ctx is not None and getattr(ctx, "lingshu_in_flight_entered", False):
            tracker = getattr(raw_request.app.ctx, "in_flight_tracker", None)
            if tracker is not None:
                try:
                    tracker.exit()
                except Exception:
                    pass
            setattr(ctx, "lingshu_in_flight_entered", False)
        reset_request_context(raw_request)


async def finish_request_context(raw_request):
    await finalize_request_context(raw_request)


def detach_request_context_after_task(raw_request):
    """Synchronous last-resort leak prevention.

    Only detaches references; never resets ContextVar tokens since the owning
    task context may be gone.  All async cleanup is handled by the finalizer.
    """
    ctx = getattr(raw_request, "ctx", None)
    if ctx is None:
        return
    if getattr(ctx, "lingshu_finalized", False):
        return
    setattr(ctx, "lingshu_finalized", True)

    if getattr(ctx, "lingshu_in_flight_entered", False):
        tracker = getattr(raw_request.app.ctx, "in_flight_tracker", None)
        if tracker is not None:
            try:
                tracker.exit()
            except Exception:
                pass
        setattr(ctx, "lingshu_in_flight_entered", False)

    context = get_request_context(raw_request)
    if context is not None:
        context.detach_after_task()
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


def _is_health_path(request) -> bool:
    return getattr(request, "path", "") in {"/live", "/ready", "/health"}


def _is_static_route(request) -> bool:
    route = getattr(request, "route", None)
    extra = getattr(route, "extra", None)
    return bool(getattr(extra, "static", False))


def _route_policy_for_request(raw_app, request) -> CompiledRoutePolicy:
    route_name = _request_route_name(raw_app, request)
    if not route_name:
        return CompiledRoutePolicy(
            route_name="not_found",
            public=True,
            auth_required=False,
            maintenance_check=False,
            timeout=10.0,
            body_limit=None,
            audit_level="none",
        )
    if _is_static_route(request):
        return CompiledRoutePolicy(
            route_name=route_name or "static",
            public=True,
            auth_required=False,
            maintenance_check=False,
            timeout=10.0,
            body_limit=None,
            audit_level="none",
        )
    compiled = getattr(raw_app.ctx, "route_policies", None)
    if compiled is not None and route_name:
        return compiled.for_route(route_name)
    raise LookupError(f"No compiled route policy for {route_name or 'unknown'}")


def _lifecycle_state(raw_app) -> str:
    lifecycle = getattr(raw_app.ctx, "lifecycle", None)
    state = getattr(lifecycle, "state", None)
    return getattr(state, "value", "ready")


def install_context_middleware(raw_app):
    @raw_app.middleware("request")
    async def bind_lingshu_context(request):
        request_id = get_request_id(request)
        try:
            route_policy = _route_policy_for_request(raw_app, request)
        except Exception:
            logger = get_optional_resource(raw_app, "logger")
            if logger is not None:
                logger.error("Missing compiled route policy", extra={"route_name": _request_route_name(raw_app, request), "request_id": request_id})
            return json_response(
                {"request_id": request_id},
                code=990001,
                msg="Route policy is not compiled",
                status=500,
            )
        execution_context = RequestExecutionContext.child(
            request_id=request_id,
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
        lifecycle = getattr(raw_app.ctx, "lifecycle", None)
        if not _is_health_path(request) and not _is_static_route(request) and getattr(lifecycle, "ready", False):
            tracker = getattr(raw_app.ctx, "in_flight_tracker", None)
            if tracker is not None:
                tracker.enter()
                request.ctx.lingshu_in_flight_entered = True
        task = asyncio.current_task()
        if task is not None:
            # Covers cancellation/disconnect paths that do not produce a response
            # and may bypass Sanic's ordinary exception lifecycle.
            task.add_done_callback(
                lambda _task, raw_request=request: detach_request_context_after_task(raw_request),
            )

    @raw_app.middleware("response")
    async def reset_lingshu_context(request, response):
        await finish_request_context(request)

    @raw_app.signal("http.lifecycle.response")
    async def reset_lingshu_context_after_response(request, response, **_):
        await finish_request_context(request)

    @raw_app.signal("http.lifecycle.exception")
    async def reset_lingshu_context_after_exception(request, exception, **_):
        if request is not None:
            await finish_request_context(request)
