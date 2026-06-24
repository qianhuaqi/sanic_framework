#!/usr/bin/env python
# -*- coding: utf-8 -*-

from framework.app import create_app


app = create_app()


if __name__ == "__main__":
    config = app.ctx.config
    app.run(host=config.host, port=config.port, debug=config.debug, workers=config.workers)
