import asyncio
from types import SimpleNamespace

import pytest

from lingshu.database.dependencies import DatabaseDependencyError
from lingshu.database.dependencies import require_database_package
from lingshu.database.mongo import MongoDB
from lingshu.database.mysql import MySQLDatabase
from lingshu.database.redis import RedisManager
from lingshu.extensions import mongo
from lingshu.extensions import mysql
from lingshu.extensions import redis
from lingshu.system import sanic_adapter


class App:
    def __init__(self, enabled_databases):
        self.ctx = SimpleNamespace(
            config=SimpleNamespace(
                enabled_databases=enabled_databases,
                mysql={},
                redis={},
                mongo={},
            )
        )


def test_missing_database_dependency_has_actionable_message(monkeypatch):
    def fake_import_module(import_path):
        raise ModuleNotFoundError("No module named 'redis'", name="redis")

    monkeypatch.setattr("lingshu.database.dependencies.importlib.import_module", fake_import_module)

    with pytest.raises(DatabaseDependencyError) as exc:
        require_database_package("redis.asyncio", "redis", "redis")

    message = str(exc.value)
    assert "Database 'redis' is enabled" in message
    assert "pip install redis" in message
    assert "REDIS_ENABLED=false" in message


def test_disabled_database_extensions_do_not_import_drivers(monkeypatch):
    async def scenario():
        app = App(enabled_databases=[])

        monkeypatch.setattr(MySQLDatabase, "__init__", lambda self, config: (_ for _ in ()).throw(AssertionError()))
        monkeypatch.setattr(RedisManager, "__init__", lambda self, config: (_ for _ in ()).throw(AssertionError()))
        monkeypatch.setattr(MongoDB, "__init__", lambda self, config: (_ for _ in ()).throw(AssertionError()))

        await mysql.setup(app)
        await redis.setup(app)
        await mongo.setup(app)

        assert sanic_adapter.get_optional_resource(app, "mysql") is None
        assert sanic_adapter.get_optional_resource(app, "redis") is None
        assert sanic_adapter.get_optional_resource(app, "mongo") is None

    asyncio.run(scenario())
