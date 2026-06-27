from importlib import import_module
import os
from pathlib import Path
from types import ModuleType

from sanic import Sanic
from sanic.exceptions import SanicException

from lingshu.config import load_config
from lingshu.exception import APIException, get_error_message
from lingshu.lifecycle import register_lifecycle
from lingshu.logging import setup_logging
from lingshu.middleware_registry import register_middleware
from lingshu.response import json_response
from lingshu.router import compile_route_policies, register_blueprints
from lingshu.system import sanic_adapter
from lingshu.runtime import run_app


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


def _register_public_static(app):
    root = Path.cwd()
    public_dir = root / "public"
    docs_dir = public_dir / "docs"
    if public_dir.exists():
        app.static("/public", str(public_dir), name="public")
    if docs_dir.exists():
        app.static("/docs", str(docs_dir), name="docs")


def create_app():
    config = load_config()
    app = Sanic(config.app_name)
    sanic_adapter.set_app_config(app, config)
    setup_logging(app)
    register_middleware(app)
    sanic_adapter.install_context_middleware(app)

    from lingshu.system.auth.middleware import install_authentication_middleware
    install_authentication_middleware(app)

    from lingshu.system.auth.tenant.middleware import install_tenant_middleware
    install_tenant_middleware(app)

    register_blueprints(app, _get_project_blueprints(config))
    register_lifecycle(app, _get_project_extension_modules())
    _register_public_static(app)
    compile_route_policies(app)

    @app.exception(APIException)
    async def handle_api_exception(request, exception):
        await sanic_adapter.finish_request_context(request)
        return json_response(
            data=exception.data,
            code=exception.code,
            msg=exception.msg,
            status=exception.status_code,
        )

    @app.exception(Exception)
    async def handle_unknown_exception(request, exception):
        await sanic_adapter.finish_request_context(request)
        if isinstance(exception, SanicException):
            status_code = getattr(exception, "status_code", 500)
            if status_code < 500:
                return json_response(code=status_code, msg=str(exception), status=status_code)
        logger = sanic_adapter.get_optional_resource(app, "logger")
        if logger is not None:
            logger.error("Unhandled exception", exc_info=(type(exception), exception, exception.__traceback__))
        return json_response(
            code=990000,
            msg=get_error_message(request, 990000),
            status=500,
        )

    return app


class _AppModule(ModuleType):
    @property
    def raw(self):
        from lingshu.system.context import get_current_app

        return get_current_app()


def _install_module_facade():
    import sys

    sys.modules[__name__].__class__ = _AppModule


_install_module_facade()


__all__ = ["create_app", "run_app"]
