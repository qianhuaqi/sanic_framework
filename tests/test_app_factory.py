from framework.app import create_app


def test_app_factory_attaches_config_and_request_id_middleware():
    app = create_app()
    assert hasattr(app.ctx, "config")
    assert any(middleware for middleware in app.request_middleware)
