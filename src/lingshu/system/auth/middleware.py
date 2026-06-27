"""Authentication security entry point middleware.

This module installs the authentication gate into the Sanic request lifecycle.
It runs after the execution context middleware (which binds
RequestExecutionContext) and before the deadline-wrapped route handler.

Policy:
- public routes (from CompiledRoutePolicy) are exempt from authentication.
- non-public routes require authentication when an AuthenticatorChain is
  registered on the app.
- if no AuthenticatorChain is registered, the middleware is transparent
  (the app has not opted into authentication yet).
- when a chain IS registered and a non-public route is accessed:
  - authentication runs exactly once per request.
  - the first SUCCESS short-circuits and binds the Principal.
  - MISSING, MALFORMED, INVALID, EXPIRED, REVOKED all produce 401.
  - INTERNAL_ERROR produces a safe 401 that never leaks details.
- the Principal is bound to a ContextVar for concurrent isolation.
- cleanup is handled by the existing finalize_request_context path.
- 401 responses carry WWW-Authenticate, stable error codes, and never
  leak tokens, secrets, exception text, or internal class names.
"""

from __future__ import annotations

import json as _json
from typing import Any

from lingshu.response import json_response
from lingshu.system.auth.authenticator import AuthenticatorChain
from lingshu.system.auth.context import bind_principal
from lingshu.system.auth.result import AuthResult, AuthenticationOutcome
from lingshu.system.sanic_adapter import (
    get_request_execution_context,
)


_RESULT_ERROR_CODE: dict[AuthResult, int] = {
    AuthResult.MISSING: 990110,
    AuthResult.MALFORMED: 990111,
    AuthResult.INVALID: 990112,
    AuthResult.EXPIRED: 990113,
    AuthResult.REVOKED: 990114,
    AuthResult.INTERNAL_ERROR: 990115,
}

_RESULT_DEFAULT_MSG: dict[AuthResult, str] = {
    AuthResult.MISSING: "Authentication credential is missing",
    AuthResult.MALFORMED: "Authentication credential is malformed",
    AuthResult.INVALID: "Authentication credential is invalid",
    AuthResult.EXPIRED: "Authentication credential has expired",
    AuthResult.REVOKED: "Authentication credential has been revoked",
    AuthResult.INTERNAL_ERROR: "Authentication service error",
}


def _build_www_authenticate(outcome: AuthenticationOutcome) -> str:
    """Build the WWW-Authenticate header value per RFC 6750."""
    error = outcome.result.www_authenticate_error
    desc = outcome.safe_description
    safe_desc = desc.replace('"', "'").replace("\n", " ").replace("\r", "")[:200]
    return f'Bearer error="{error}", error_description="{safe_desc}"'


def _build_401_response(request, outcome: AuthenticationOutcome, *, override_code: int | None = None):
    """Build a stable 401 JSON response with WWW-Authenticate header."""
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
        error_code = _RESULT_ERROR_CODE.get(outcome.result, 990112)
    default_msg = _RESULT_DEFAULT_MSG.get(outcome.result, "Authentication credential is invalid")

    msg = default_msg
    try:
        from lingshu.exception import get_error_message
        resolved = get_error_message(request, error_code, default=default_msg)
        if resolved:
            msg = resolved
    except Exception:
        pass

    response = json_response(
        data=data if data else None,
        code=error_code,
        msg=msg,
        status=401,
    )
    response.headers["WWW-Authenticate"] = _build_www_authenticate(outcome)
    return response


def get_authenticator_chain(raw_app) -> AuthenticatorChain | None:
    return getattr(raw_app.ctx, "authenticator_chain", None)


def set_authenticator_chain(raw_app, chain: AuthenticatorChain):
    raw_app.ctx.authenticator_chain = chain


def install_authentication_middleware(raw_app):
    """Install the authentication security gate as a request middleware.

    Must be called after ``install_context_middleware`` so the execution
    context and compiled route policy are available.
    """

    @raw_app.middleware("request")
    async def authenticate_request(request):
        exec_ctx = getattr(request.ctx, "lingshu_execution_context", None)
        if exec_ctx is None:
            return None

        route_policy = exec_ctx.route_policy

        is_public = getattr(route_policy, "public", False)
        auth_required = getattr(route_policy, "auth_required", True)

        if is_public or not auth_required:
            return None

        chain = get_authenticator_chain(raw_app)

        # No chain registered: authentication not opted in.  Transparent.
        if chain is None:
            return None

        # Chain registered but empty: fail closed — scheme not registered.
        if chain.is_empty:
            outcome = AuthenticationOutcome(
                result=AuthResult.MISSING,
                error_description="No authentication scheme is registered",
            )
            response = _build_401_response(request, outcome, override_code=990116)
            await _finalize_for_auth(request)
            return response

        try:
            outcome = await chain.authenticate(request)
        except Exception:
            outcome = AuthenticationOutcome.internal_error(
                authenticator_id="chain",
                error=None,
            )

        if outcome.is_success and outcome.principal is not None:
            binding = bind_principal(outcome.principal)
            binding.__enter__()
            request.ctx.lingshu_principal_binding = binding
            return None

        response = _build_401_response(request, outcome)
        await _finalize_for_auth(request)
        return response


async def _finalize_for_auth(request):
    """Ensure context cleanup runs after a 401 short-circuit response."""
    from lingshu.system.sanic_adapter import finalize_request_context
    await finalize_request_context(request)
