from __future__ import annotations

from sanic import Blueprint

from app.v1.model.demo import DemoModel
from framework.exception import APIException
from framework.response import json_response


bp = Blueprint("v1_demo", url_prefix="/v1/demo")


def _get_mysql(request):
    db = getattr(request.app.ctx, "mysql", None)
    if db is None:
        raise APIException(errcode=503000, errmsg="mysql is not enabled", status_code=503)
    return db


def _get_json_payload(request):
    payload = request.json or {}
    if not isinstance(payload, dict):
        raise APIException(errcode=400000, errmsg="invalid json body", status_code=400)
    return payload


@bp.get("/")
async def index(request):
    _get_mysql(request)
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 10))
    use_master = request.args.get("use_master", "").lower() in {"1", "true", "yes", "on"}
    result = await DemoModel(request).get_pagination(page=page, size=size, use_master=use_master)
    return json_response(result)


@bp.get("/<data_id>")
async def info(request, data_id):
    _get_mysql(request)
    use_cache = request.args.get("use_cache", "1").lower() not in {"0", "false", "no", "off"}
    use_master = request.args.get("use_master", "").lower() in {"1", "true", "yes", "on"}
    item = await DemoModel(request).get_one(data_id, use_master=use_master, use_cache=use_cache)
    if item is None:
        raise APIException(errcode=404000, errmsg="demo row not found", status_code=404)
    return json_response(item)


@bp.post("/")
async def create(request):
    _get_mysql(request)
    payload = _get_json_payload(request)
    data_id = await DemoModel(request).insert(**payload)
    return json_response({"id": data_id, "payload": payload}, status=201)


@bp.put("/<data_id>")
async def update(request, data_id):
    _get_mysql(request)
    payload = _get_json_payload(request)
    if not payload:
        raise APIException(errcode=400002, errmsg="update payload is empty", status_code=400)
    result = await DemoModel(request).update(data_id, **payload)
    return json_response({"id": data_id, "updated": result})


@bp.patch("/<data_id>")
async def partial_update(request, data_id):
    _get_mysql(request)
    payload = _get_json_payload(request)
    if not payload:
        raise APIException(errcode=400002, errmsg="update payload is empty", status_code=400)
    result = await DemoModel(request).update(data_id, **payload)
    return json_response({"id": data_id, "updated": result})


@bp.delete("/<data_id>")
async def delete(request, data_id):
    _get_mysql(request)
    result = await DemoModel(request).delete(data_id)
    return json_response({"id": data_id, "deleted": result})
