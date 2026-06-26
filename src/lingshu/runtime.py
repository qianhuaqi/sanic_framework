from __future__ import annotations


def run_app(raw_app):
    from lingshu.system.sanic_adapter import get_app_config

    config = get_app_config(raw_app)
    return raw_app.run(host=config.host, port=config.port, debug=config.debug, workers=config.workers)


def run(raw_app):
    return run_app(raw_app)
