#!/usr/bin/env python
# -*- coding: utf-8 -*-

from lingshu.app import create_app
from lingshu.system import sanic_adapter


app = create_app()


if __name__ == "__main__":
    config = sanic_adapter.get_app_config(app)
    app.run(host=config.host, port=config.port, debug=config.debug, workers=config.workers)
