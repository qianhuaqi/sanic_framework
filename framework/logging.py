import logging


def setup_logging(app):
    logger = logging.getLogger(app.ctx.config.app_name)
    logger.setLevel(logging.DEBUG if app.ctx.config.debug else logging.INFO)
    app.ctx.logger = logger
