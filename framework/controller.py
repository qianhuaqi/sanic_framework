from __future__ import annotations

from framework.exception import raise_code


def require_mysql(request):
    db = getattr(request.app.ctx, "mysql", None)
    if db is None:
        raise_code(request, 990201, status_code=503)
    return db


def json_payload(request):
    payload = request.json or {}
    if not isinstance(payload, dict):
        raise_code(request, 991110, status_code=400)
    return payload


def require_payload(request):
    payload = json_payload(request)
    if not payload:
        raise_code(request, 991111, status_code=400)
    return payload
