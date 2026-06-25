import importlib
import asyncio
import json

import pytest
from sanic import Blueprint

from framework.app import create_app
from framework.exception import APIException
from framework.response import json_response


def _body(response):
    return json.loads(response.body)


def test_json_response_uses_only_code_msg_data_by_default():
    response = json_response()

    assert response.status == 200
    assert _body(response) == {"code": 0, "msg": "ok", "data": {}}
    assert "errcode" not in _body(response)
    assert "errmsg" not in _body(response)


def test_json_response_preserves_falsey_data_values():
    assert _body(json_response(data=0, code=7, msg="zero")) == {"code": 7, "msg": "zero", "data": 0}
    assert _body(json_response(data=False, code=7, msg="false")) == {"code": 7, "msg": "false", "data": False}
    assert _body(json_response(data=[], code=7, msg="list")) == {"code": 7, "msg": "list", "data": []}
    assert _body(json_response(data="", code=7, msg="empty")) == {"code": 7, "msg": "empty", "data": ""}


def test_json_response_rejects_legacy_error_keyword_arguments():
    with pytest.raises(TypeError):
        json_response(errcode=991111)
    with pytest.raises(TypeError):
        json_response(errmsg="bad")


def test_api_exception_uses_only_code_msg_data_contract():
    exc = APIException(code=991111, msg="bad", status_code=400, data=False)

    assert exc.code == 991111
    assert exc.msg == "bad"
    assert exc.status_code == 400
    assert exc.data is False
    assert not hasattr(exc, "errcode")
    assert not hasattr(exc, "errmsg")


def test_api_exception_preserves_falsey_data_values():
    assert APIException(code=1, msg="zero", data=0).data == 0
    assert APIException(code=1, msg="false", data=False).data is False
    assert APIException(code=1, msg="list", data=[]).data == []


def test_api_exception_rejects_legacy_keyword_arguments():
    with pytest.raises(TypeError):
        APIException(errcode=991111)
    with pytest.raises(TypeError):
        APIException(code=991111, errmsg="bad")


def test_legacy_middleware_api_exception_module_is_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("framework.middleware.api_exception")


def test_api_exception_response_uses_code_msg_data_shape():
    app = create_app()
    bp = Blueprint("response_contract_api_exception")

    @bp.get("/contract/api-error")
    async def api_error(request):
        raise APIException(code=991111, msg="payload required", status_code=400, data=False)

    app.blueprint(bp)

    async def scenario():
        return await app.asgi_client.get("/contract/api-error")

    _, response = asyncio.run(scenario())

    assert response.status == 400
    assert response.json == {"code": 991111, "msg": "payload required", "data": False}


def test_404_does_not_return_system_error_message():
    app = create_app()

    async def scenario():
        return await app.asgi_client.get("/missing-response-contract-route")

    _, response = asyncio.run(scenario())

    assert response.status == 404
    assert response.json is None or response.json.get("code") != 990000
    if response.json:
        assert response.json.get("msg") != "System error"


def test_unknown_exception_returns_safe_500_response():
    app = create_app()
    bp = Blueprint("response_contract_unknown_exception")

    @bp.get("/contract/boom")
    async def boom(request):
        raise RuntimeError("secret boom text")

    app.blueprint(bp)

    async def scenario():
        return await app.asgi_client.get("/contract/boom")

    _, response = asyncio.run(scenario())

    assert response.status == 500
    assert response.json["code"] == 990000
    assert "secret boom text" not in response.json["msg"]
    assert set(response.json) == {"code", "msg", "data"}
