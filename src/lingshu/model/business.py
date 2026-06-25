from __future__ import annotations

from lingshu import app, db, logger, request


class BusinessModel:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "table_name" in cls.__dict__:
            raise TypeError("BusinessModel must not declare table_name")

    @property
    def request(self):
        return request.raw

    @property
    def app(self):
        return app.raw

    @property
    def db(self):
        return db.mysql

    @property
    def redis(self):
        return db.optional("redis")

    @property
    def logger(self):
        return logger
