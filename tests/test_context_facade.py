import asyncio
import importlib
import logging
from types import SimpleNamespace

import pytest
from sanic import Sanic

import lingshu
from lingshu import abort, app, config, db, language, logger, request
from lingshu.exception import APIException
from lingshu.middleware_registry import register_middleware
from lingshu.response import json_response
from lingshu.system import sanic_adapter
from lingshu.system.context import app_context, request_context
from lingshu.system.errors import NoAppContextError, NoRequestContextError, ResourceNotConfiguredError


def _app(name="demo", debug=False):
    raw = SimpleNamespace(ctx=SimpleNamespace())
    sanic_adapter.set_app_config(raw, SimpleNamespace(app_name=name, debug=debug, language="zh-CN"))
    sanic_adapter.set_app_logger(raw, logging.getLogger(name))
    return raw


def _request(raw_app, path="/v1/demo", method="GET", user=None):
    return SimpleNamespace(
        app=raw_app,
        path=path,
        method=method,
        headers={"X-Request-ID": "header-id"},
        args={"page": ["1"]},
        json={"ok": True},
        ctx=SimpleNamespace(g=user),
    )


def test_import_lingshu_and_public_facade_only():
    assert lingshu.__all__ == ["APIException", "abort", "app", "config", "db", "language", "logger", "request"]
    assert importlib.util.find_spec("framework") is None
    assert logger.info


def test_no_context_errors_are_clear():
    logger.info("logger works without app context")

    with pytest.raises(NoAppContextError):
        _ = config.debug
    with pytest.raises(NoAppContextError):
        _ = app.raw
    with pytest.raises(NoRequestContextError):
        _ = request.raw
    with pytest.raises(NoAppContextError):
        _ = db.mysql
    with pytest.raises(NoAppContextError):
        language.get(991111)
    with pytest.raises(NoRequestContextError):
        _ = request.id


def test_logger_proxy_raises_when_app_is_present_but_logger_is_missing():
    raw_app = SimpleNamespace(ctx=SimpleNamespace(config=SimpleNamespace(app_name="bad", debug=False, language="zh-CN")))

    with app_context(raw_app):
        with pytest.raises(AttributeError):
            logger.info("should surface logger configuration errors")


def test_app_context_facades_and_resource_errors():
    raw_app = _app(debug=True)
    sanic_adapter.set_resource(raw_app, "mysql", object())

    with app_context(raw_app):
        assert app.raw is raw_app
        assert config.debug is True
        assert config["DEBUG"] is True
        assert db.mysql is sanic_adapter.get_resource(raw_app, "mysql")
        assert "请求参数不能为空" == language.get(991111)
        with pytest.raises(ResourceNotConfiguredError):
            _ = db.redis


def test_config_facade_returns_read_only_views():
    raw_app = SimpleNamespace(
        ctx=SimpleNamespace(
            config=SimpleNamespace(
                app_name="demo",
                debug=False,
                language="zh-CN",
                enabled_databases=["mysql", "redis"],
                cors_origins=["https://a.test"],
                mysql={"host": "localhost", "nested": {"port": 3306}},
            )
        )
    )

    with app_context(raw_app):
        assert config.enabled_databases == ("mysql", "redis")
        assert config.cors_origins == ("https://a.test",)
        assert config.mysql["host"] == "localhost"
        assert config.mysql["nested"]["port"] == 3306
        with pytest.raises(AttributeError):
            config.enabled_databases.append("mongo")  # type: ignore[attr-defined]
        with pytest.raises(TypeError):
            config.mysql["host"] = "changed"  # type: ignore[index]


def test_nested_app_context_restores_outer_app():
    outer = _app("outer", debug=False)
    inner = _app("inner", debug=True)

    with app_context(outer):
        assert config.debug is False
        with app_context(inner):
            assert app.raw is inner
            assert config.debug is True
        assert app.raw is outer
        assert config.debug is False


def test_request_context_facade_and_cleanup():
    raw_app = _app()
    raw_request = _request(raw_app, path="/v1/demo", method="POST", user={"id": 7})

    with request_context(raw_app, raw_request, request_id="rid-1", user=raw_request.ctx.g):
        assert request.raw is raw_request
        assert request.id == "rid-1"
        assert request.method == "POST"
        assert request.path == "/v1/demo"
        assert request.headers["X-Request-ID"] == "header-id"
        assert request.args["page"] == ["1"]
        assert request.json == {"ok": True}
        assert request.user == {"id": 7}

    with pytest.raises(NoRequestContextError):
        _ = request.raw
    with pytest.raises(NoRequestContextError):
        _ = request.id


def test_request_context_preserves_falsey_user_values():
    raw_app = _app()
    raw_request = _request(raw_app, user=0)

    with request_context(raw_app, raw_request, request_id="rid-3", user=0):
        assert request.user == 0
        assert request.id == "rid-3"


def test_abort_uses_language_and_code_msg_data_contract():
    raw_app = _app()
    raw_request = _request(raw_app)

    with request_context(raw_app, raw_request, request_id="rid-2"):
        with pytest.raises(APIException) as exc:
            abort(991111, status=400, data=False)

    assert exc.value.code == 991111
    assert exc.value.msg == "请求参数不能为空"
    assert exc.value.status_code == 400
    assert exc.value.data is False


def test_concurrent_request_contexts_do_not_cross():
    raw_app = _app()

    async def worker(path, request_id):
        raw_request = _request(raw_app, path=path)
        with request_context(raw_app, raw_request, request_id=request_id):
            await asyncio.sleep(0)
            return request.path, request.id

    async def scenario():
        return await asyncio.gather(
            worker("/v1/demo", "a"),
            worker("/v1_admin/demo", "b"),
        )

    results = asyncio.run(scenario())

    assert results == [("/v1/demo", "a"), ("/v1_admin/demo", "b")]


def test_multi_app_resource_isolation():
    app_a = _app("a", debug=False)
    app_b = _app("b", debug=True)
    mysql_a = object()
    mysql_b = object()
    sanic_adapter.set_resource(app_a, "mysql", mysql_a)
    sanic_adapter.set_resource(app_b, "mysql", mysql_b)

    with app_context(app_a):
        assert config.debug is False
        assert db.mysql is mysql_a
    with app_context(app_b):
        assert config.debug is True
        assert db.mysql is mysql_b


def test_request_context_clears_after_real_sanic_request(tmp_path):
    raw_app = Sanic("integration")
    sanic_adapter.set_app_config(
        raw_app,
        SimpleNamespace(
            app_name="integration",
            debug=False,
            language="zh-CN",
            log_level="INFO",
            log_to_file=False,
            log_path=str(tmp_path / "logs"),
            log_file="app.log",
            log_formatter="%(message)s",
            log_max_bytes=1024,
            log_backup_count=1,
        ),
    )
    sanic_adapter.set_app_logger(raw_app, logging.getLogger("integration"))
    register_middleware(raw_app)
    sanic_adapter.install_context_middleware(raw_app)

    @raw_app.get("/probe")
    async def probe(request_):
        return json_response({"request_id": request.id})

    @raw_app.get("/boom")
    async def boom(request_):
        raise RuntimeError("boom")

    @raw_app.exception(Exception)
    async def handle_exception(request_, exception):
        sanic_adapter.reset_request_context(request_)
        return json_response(code=990000, msg=str(exception), status=500)

    async def scenario():
        _, response = await raw_app.asgi_client.get("/probe")
        assert response.status == 200
        assert response.json["data"]["request_id"]
        with pytest.raises(NoRequestContextError):
            _ = request.raw

        _, response = await raw_app.asgi_client.get("/boom")
        assert response.status == 500
        assert response.json["code"] == 990000
        with pytest.raises(NoRequestContextError):
            _ = request.raw

    asyncio.run(scenario())


def test_request_context_clears_when_response_middleware_fails(tmp_path):
    raw_app = Sanic("response-middleware-failure")
    sanic_adapter.set_app_config(
        raw_app,
        SimpleNamespace(
            app_name="response-middleware-failure",
            debug=False,
            language="zh-CN",
            log_level="INFO",
            log_to_file=False,
            log_path=str(tmp_path / "logs"),
            log_file="app.log",
            log_formatter="%(message)s",
            log_max_bytes=1024,
            log_backup_count=1,
        ),
    )
    sanic_adapter.set_app_logger(raw_app, logging.getLogger("response-middleware-failure"))
    sanic_adapter.install_context_middleware(raw_app)

    @raw_app.middleware("response")
    async def later_response_middleware(request_, response):
        assert request.id
        raise RuntimeError("response middleware failed")

    @raw_app.get("/probe")
    async def probe(request_):
        return json_response({"ok": True})

    @raw_app.exception(Exception)
    async def handle_exception(request_, exception):
        return json_response(code=990000, msg=str(exception), status=500)

    async def scenario():
        _, response_ = await raw_app.asgi_client.get("/probe")
        assert response_.status == 200
        with pytest.raises(NoRequestContextError):
            _ = request.raw
        with pytest.raises(NoRequestContextError):
            _ = request.id

    asyncio.run(scenario())
