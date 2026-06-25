from lingshu.app import create_app
from lingshu.system import sanic_adapter


def test_app_factory_attaches_config_and_request_id_middleware():
    app = create_app()
    assert sanic_adapter.get_app_config(app).app_name
    assert any(middleware for middleware in app.request_middleware)
