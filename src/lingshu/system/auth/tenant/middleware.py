"""Tenant resolution security entry point middleware.

Policy (fail-closed):
- Only runs on tenant_required routes after authentication has succeeded.
- If authentication failed or no Principal is bound, the auth middleware
  already returned a 401 — this middleware never runs for that request.
- Chain not registered OR empty: 403 with error code 990124.
- Chain registered: resolve; first SUCCESS binds TenantContext,
  any failure produces 403.
- 403 responses carry stable error codes and never leak tenant claims,
  validator exceptions, or internal class names.
"""

from __future__ import annotations

from typing import Any

from lingshu.response import json_response
from lingshu.system.auth.tenant.binding import bind_tenant
from lingshu.system.auth.tenant.resolver import TenantResolverChain
from lingshu.system.auth.tenant.result import (
    TenantResolutionOutcome,
    TenantResolutionResult,
)
from lingshu.system.sanic_adapter import (
    get_request_execution_context,
)


_RESULT_ERROR_CODE: dict[TenantResolutionResult, int] = {
    TenantResolutionResult.MISSING: 990120,
    TenantResolutionResult.MALFORMED: 990121,
    TenantResolutionResult.FORBIDDEN: 990122,
    TenantResolutionResult.INTERNAL_ERROR: 990123,
}

_RESULT_DEFAULT_MSG: dict[TenantResolutionResult, str] = {
    TenantResolutionResult.MISSING: "Tenant context is missing",
    TenantResolutionResult.MALFORMED: "Malformed tenant identifier",
    TenantResolutionResult.FORBIDDEN: "Tenant access forbidden",
    TenantResolutionResult.INTERNAL_ERROR: "Tenant resolver internal error",
}


def _build_403_response(request, outcome: TenantResolutionOutcome, *, override_code: int | None = None):
    """Build a stable 403 JSON response."""
    exec_ctx = None
    try:
        exec_ctx = get_request_execution_context(request)
    except Exception:
        pass

    data: dict[str, Any] = {}
    if exec_ctx is not None:
        data["request_id"] = exec_ctx.request_id
        if exec_ctx.trace_id:
            data["trace_id"] = exec_ctx.trace_id

    if override_code is not None:
        error_code = override_code
    else:
        error_code = _RESULT_ERROR_CODE.get(outcome.result, 990121)
    default_msg = _RESULT_DEFAULT_MSG.get(outcome.result, "Tenant resolution failed")

    msg = default_msg
    try:
        from lingshu.exception import get_error_message
        resolved = get_error_message(request, error_code, default=default_msg)
        if resolved:
            msg = resolved
    except Exception:
        pass

    return json_response(
        data=data if data else None,
        code=error_code,
        msg=msg,
        status=403,
    )


def get_tenant_resolver_chain(raw_app) -> TenantResolverChain | None:
    return getattr(raw_app.ctx, "tenant_resolver_chain", None)


def set_tenant_resolver_chain(raw_app, chain: TenantResolverChain):
    raw_app.ctx.tenant_resolver_chain = chain


def install_tenant_middleware(raw_app):
    """Install the tenant resolution gate as a request middleware.

    Must be called after ``install_authentication_middleware`` so the
    Principal is already bound for authenticated requests.

    Idempotent: repeated calls do not install additional middleware.
    """
    if getattr(raw_app.ctx, "lingshu_tenant_middleware_installed", False):
        return

    @raw_app.middleware("request")
    async def resolve_tenant(request):
        exec_ctx = getattr(request.ctx, "lingshu_execution_context", None)
        if exec_ctx is None:
            return None

        route_policy = exec_ctx.route_policy

        tenant_required = getattr(route_policy, "tenant_required", False)
        if not tenant_required:
            return None

        from lingshu.system.auth.context import current_principal
        principal = current_principal.get()

        if principal is None:
            return None

        chain = get_tenant_resolver_chain(raw_app)

        if chain is None or chain.is_empty:
            outcome = TenantResolutionOutcome(
                result=TenantResolutionResult.MISSING,
                error_description="No tenant resolver is registered",
            )
            response = _build_403_response(request, outcome, override_code=990124)
            await _finalize_for_tenant(request)
            return response

        try:
            outcome = await chain.resolve(request, principal)
        except Exception:
            outcome = TenantResolutionOutcome.internal_error(
                resolver_id="chain",
                error=None,
            )

        if outcome.is_success and outcome.tenant_context is not None:
            binding = bind_tenant(outcome.tenant_context)
            binding.__enter__()
            request.ctx.lingshu_tenant_binding = binding
            return None

        response = _build_403_response(request, outcome)
        await _finalize_for_tenant(request)
        return response

    raw_app.ctx.lingshu_tenant_middleware_installed = True


async def _finalize_for_tenant(request):
    """Ensure context cleanup runs after a 403 short-circuit response."""
    from lingshu.system.sanic_adapter import finalize_request_context
    await finalize_request_context(request)
