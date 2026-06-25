import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from lingshu.system import sanic_adapter


def setup_logging(app):
    config = sanic_adapter.get_app_config(app)
    logger = logging.getLogger("lingshu")
    level = getattr(logging, str(config.log_level).upper(), logging.INFO)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(config.log_formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if config.log_to_file:
        log_dir = Path(config.log_path)
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / config.log_file,
            maxBytes=config.log_max_bytes,
            backupCount=config.log_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    sanic_adapter.set_resource(app, "logger", logger)
    return logger
