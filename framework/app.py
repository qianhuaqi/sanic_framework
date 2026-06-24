from importlib import import_module
import os

from sanic import Sanic

from framework.config import load_config
from framework.exception import APIException
from framework.lifecycle import register_lifecycle
from framework.logging import setup_logging
from framework.middleware_registry import register_middleware
from framework.response import json_response
from framework.router import register_blueprints


def _load_project_bootstrap():
    module_name = os.getenv("APP_BOOTSTRAP_MODULE", "app.bootstrap")
    return import_module(module_name)


def _get_project_blueprints(config):
    bootstrap = _load_project_bootstrap()
    get_blueprints = getattr(bootstrap, "get_feature_blueprints", None)
    if get_blueprints is None:
        return []
    return get_blueprints(config)


def _get_project_extension_modules():
    bootstrap = _load_project_bootstrap()
    get_modules = getattr(bootstrap, "get_extension_modules", None)
    if get_modules is None:
        return []
    return get_modules()


def create_app():
    config = load_config()
    app = Sanic(config.app_name)
    app.ctx.config = config
    setup_logging(app)
    register_middleware(app)
    register_lifecycle(app, _get_project_extension_modules())

    register_blueprints(app, _get_project_blueprints(config))

    @app.exception(APIException)
    async def handle_api_exception(request, exception):
        return json_response(
            data=exception.data,
            errcode=exception.errcode,
            errmsg=exception.errmsg,
            status=exception.status_code,
        )

    return app
