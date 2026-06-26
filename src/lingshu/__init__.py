from lingshu.exception import APIException, raise_code
from lingshu.system.context import get_current_app
from lingshu.system.proxies import app, config, db, logger, request


class LanguageFacade:
    def get(self, code: int | str) -> str:
        from lingshu.exception import get_error_message

        get_current_app()
        return get_error_message(None, code)


def abort(code, status=400, data=None):
    get_current_app()
    raise_code(None, code, status_code=status, data=data)


language = LanguageFacade()

__all__ = [
    "APIException",
    "abort",
    "app",
    "config",
    "db",
    "language",
    "logger",
    "request",
]
