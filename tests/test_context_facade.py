import asyncio
import importlib
import logging
from types import SimpleNamespace

import pytest

import lingshu
from lingshu import abort, app, config, db, language, logger, request
from lingshu.exception import APIException
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
