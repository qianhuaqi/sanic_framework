from sanic import Blueprint

from framework.response import json_response
from framework.router import RoutePolicy, set_blueprint_policy


bp = Blueprint("health")
set_blueprint_policy(
    bp,
    RoutePolicy(
        auth_required=False,
        signing_required=False,
        maintenance_check=False,
    ),
)


@bp.get("/")
async def root(request):
    return json_response({"status": "ok"})


@bp.get("/health")
async def health(request):
    return json_response({"status": "ok"})
