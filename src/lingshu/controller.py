from __future__ import annotations

from lingshu import db
from lingshu.exception import raise_code


def require_mysql(request):
    try:
        mysql = db.mysql
    except Exception:
        raise_code(request, 990201, status_code=503)
    return mysql


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
