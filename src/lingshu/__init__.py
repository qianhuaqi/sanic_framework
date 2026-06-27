from lingshu.exception import APIException, raise_code
from lingshu.system.context import get_current_app
from lingshu.system.proxies import app, config, db, logger, request


class LanguageFacade:
    def get(self, code: int | str) -> str:
        from lingshu.exception import get_error_message

        get_current_app()
        return get_error_message(None, code)


class AuthFacade:
    """Lazy facade over lingshu.auth public functions."""

    @property
    def principal(self):
        from lingshu.auth import get_principal
        return get_principal()

    def require_principal(self):
        from lingshu.auth import require_principal
        return require_principal()

    def configure(self, raw_app, chain):
        from lingshu.auth import configure_authentication
        return configure_authentication(raw_app, chain)


def abort(code, status=400, data=None):
    get_current_app()
    raise_code(None, code, status_code=status, data=data)


language = LanguageFacade()
auth = AuthFacade()

__all__ = [
    "APIException",
    "abort",
    "app",
    "auth",
    "config",
    "db",
    "language",
    "logger",
    "request",
]
