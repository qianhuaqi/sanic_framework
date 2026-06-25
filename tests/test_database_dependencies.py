import asyncio
from types import SimpleNamespace

import pytest

from framework.database.dependencies import DatabaseDependencyError
from framework.database.dependencies import require_database_package
from framework.database.mongo import MongoDB
from framework.database.mysql import MySQLDatabase
from framework.database.redis import RedisManager
from framework.extensions import mongo
from framework.extensions import mysql
from framework.extensions import redis


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

    monkeypatch.setattr("framework.database.dependencies.importlib.import_module", fake_import_module)

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

        assert not hasattr(app.ctx, "mysql")
        assert not hasattr(app.ctx, "redis")
        assert not hasattr(app.ctx, "mongo")

    asyncio.run(scenario())
