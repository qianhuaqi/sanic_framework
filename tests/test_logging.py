from types import SimpleNamespace

from lingshu.logging import setup_logging
from lingshu.system import sanic_adapter


def test_setup_logging_writes_to_configured_file(tmp_path):
    log_path = tmp_path / "logs"
    app = SimpleNamespace(
        ctx=SimpleNamespace(
            config=SimpleNamespace(
                app_name="test-app",
                debug=True,
                log_to_file=True,
                log_level="DEBUG",
                log_path=str(log_path),
                log_file="app.log",
                log_formatter="%(levelname)s:%(message)s",
                log_max_bytes=2048,
                log_backup_count=2,
            )
        )
    )

    setup_logging(app)
    logger = sanic_adapter.get_app_logger(app)
    logger.debug("debug message")

    for handler in logger.handlers:
        handler.flush()

    assert (log_path / "app.log").read_text(encoding="utf-8").strip() == "DEBUG:debug message"
