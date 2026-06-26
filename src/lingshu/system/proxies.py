from __future__ import annotations

import logging
from types import MappingProxyType

from lingshu.system.context import current_request_id, current_user, get_current_app, get_current_request
from lingshu.system.errors import NoAppContextError, NoRequestContextError, ResourceNotConfiguredError
from lingshu.system.sanic_adapter import get_app_config, get_app_logger, get_optional_resource, get_resource


def _freeze_value(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_value(item) for item in value)
    return value


class LoggerProxy:
    def _logger(self):
        try:
            return get_app_logger(get_current_app())
        except NoAppContextError:
            return logging.getLogger("lingshu")

    def __getattr__(self, name):
        return getattr(self._logger(), name)


class ConfigProxy:
    def _config(self):
        return get_app_config(get_current_app())

    def __getattr__(self, name):
        return _freeze_value(getattr(self._config(), name))

    def __getitem__(self, key):
        return _freeze_value(getattr(self._config(), str(key).lower()))

    def __setattr__(self, name, value):
        if name.startswith("_"):
            return super().__setattr__(name, value)
        raise AttributeError("LingShu config facade is read-only")


class AppProxy:
    @property
    def raw(self):
        return get_current_app()


class RequestProxy:
    @property
    def raw(self):
        return get_current_request()

    @property
    def id(self):
        get_current_request()
        request_id = current_request_id.get()
        if request_id is None:
            raise NoRequestContextError("No LingShu request context is active")
        return request_id

    @property
    def method(self):
        return self.raw.method

    @property
    def path(self):
        return self.raw.path

    @property
    def headers(self):
        return self.raw.headers

    @property
    def args(self):
        return self.raw.args

    @property
    def json(self):
        return self.raw.json

    @property
    def user(self):
        ctx = getattr(self.raw, "ctx", None)
        if ctx is not None and hasattr(ctx, "g"):
            return getattr(ctx, "g")
        return current_user.get()


class DatabaseProxy:
    @property
    def mysql(self):
        return get_resource(get_current_app(), "mysql")

    @property
    def redis(self):
        return get_resource(get_current_app(), "redis")

    @property
    def mongo(self):
        return get_resource(get_current_app(), "mongo")

    def optional(self, name: str):
        return get_optional_resource(get_current_app(), name)


logger = LoggerProxy()
config = ConfigProxy()
app = AppProxy()
request = RequestProxy()
db = DatabaseProxy()
