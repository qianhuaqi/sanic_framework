from __future__ import annotations

from sanic import Blueprint

from app.v1.model.demo import DemoModel
from framework.controller import require_mysql, require_payload
from framework.exception import raise_code
from framework.response import json_response


bp = Blueprint("v1_demo", url_prefix="/v1/demo")


@bp.get("/")
async def index(request):
    require_mysql(request)
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 10))
    use_master = request.args.get("use_master", "").lower() in {"1", "true", "yes", "on"}
    request.app.ctx.logger.debug("demo.index page=%s size=%s use_master=%s", page, size, use_master)
    result = await DemoModel(request).get_pagination(page=page, size=size, use_master=use_master)
    return json_response(result)


@bp.get("/<data_id>")
async def info(request, data_id):
    require_mysql(request)
    use_cache = request.args.get("use_cache", "1").lower() not in {"0", "false", "no", "off"}
    use_master = request.args.get("use_master", "").lower() in {"1", "true", "yes", "on"}
    request.app.ctx.logger.debug("demo.info id=%s use_cache=%s use_master=%s", data_id, use_cache, use_master)
    item = await DemoModel(request).get_one(data_id, use_master=use_master, use_cache=use_cache)
    if item is None:
        raise_code(request, 990202, status_code=404, default="demo row not found")
    return json_response(item)


@bp.post("/")
async def create(request):
    require_mysql(request)
    payload = require_payload(request)
    request.app.ctx.logger.info("demo.create fields=%s", sorted(payload.keys()))
    data_id = await DemoModel(request).insert(**payload)
    return json_response({"id": data_id, "payload": payload}, status=201)


@bp.put("/<data_id>")
async def update(request, data_id):
    require_mysql(request)
    payload = require_payload(request)
    request.app.ctx.logger.info("demo.update id=%s fields=%s", data_id, sorted(payload.keys()))
    result = await DemoModel(request).update(data_id, **payload)
    return json_response({"id": data_id, "updated": result})


@bp.delete("/<data_id>")
async def delete(request, data_id):
    require_mysql(request)
    request.app.ctx.logger.info("demo.delete id=%s", data_id)
    result = await DemoModel(request).delete(data_id)
    return json_response({"id": data_id, "deleted": result})
