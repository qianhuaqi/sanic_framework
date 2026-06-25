import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(app):
    logger = logging.getLogger(app.ctx.config.app_name)
    level = getattr(logging, str(app.ctx.config.log_level).upper(), logging.INFO)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(app.ctx.config.log_formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if app.ctx.config.log_to_file:
        log_dir = Path(app.ctx.config.log_path)
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / app.ctx.config.log_file,
            maxBytes=app.ctx.config.log_max_bytes,
            backupCount=app.ctx.config.log_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    app.ctx.logger = logger
