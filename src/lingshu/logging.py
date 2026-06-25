import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from lingshu.system.context import current_request_id, current_user, get_current_request
from lingshu.system import sanic_adapter
from lingshu.system.errors import NoRequestContextError


class _RequestContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = ""
        record.method = ""
        record.path = ""
        record.user_id = ""
        try:
            raw_request = get_current_request()
        except NoRequestContextError:
            return True

        request_id = current_request_id.get()
        if request_id is not None:
            record.request_id = str(request_id)
        record.method = str(getattr(raw_request, "method", "") or "")
        record.path = str(getattr(raw_request, "path", "") or "")
        user = current_user.get()
        if user is None:
            ctx = getattr(raw_request, "ctx", None)
            if ctx is not None and hasattr(ctx, "g"):
                user = getattr(ctx, "g")
        if user is not None:
            record.user_id = str(user)
        return True


def _logger_name(config, app) -> str:
    app_name = str(getattr(config, "app_name", "lingshu")).strip() or "lingshu"
    app_name = app_name.replace(" ", "_")
    return f"lingshu.{app_name}.{id(app):x}"


def setup_logging(app):
    config = sanic_adapter.get_app_config(app)
    logger = logging.getLogger(_logger_name(config, app))
    level = getattr(logging, str(config.log_level).upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    app_id = id(app)
    logger.handlers = [handler for handler in logger.handlers if getattr(handler, "_lingshu_app_id", None) != app_id]

    formatter = logging.Formatter(config.log_formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(_RequestContextFilter())
    stream_handler._lingshu_app_id = app_id
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
        file_handler.addFilter(_RequestContextFilter())
        file_handler._lingshu_app_id = app_id
        logger.addHandler(file_handler)

    sanic_adapter.set_resource(app, "logger", logger)
    return logger
