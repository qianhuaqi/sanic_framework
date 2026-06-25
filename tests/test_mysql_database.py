import asyncio
from types import SimpleNamespace

from framework.database.mysql import MySQLDatabase


class FakeCursor:
    def __init__(self, pool):
        self.pool = pool
        self.lastrowid = 42
        self.rowcount = 3

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, query, args):
        self.pool.calls.append(("execute", query, tuple(args)))

    async def fetchone(self):
        return {"pool": self.pool.label, "value": 1}

    async def fetchall(self):
        return [{"pool": self.pool.label, "value": 1}]

    async def executemany(self, query, args_list):
        self.pool.calls.append(("executemany", query, tuple(args_list)))


class FakeConn:
    def __init__(self, pool):
        self.pool = pool

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def cursor(self, _cursor_cls):
        return FakeCursor(self.pool)


class FakePool:
    def __init__(self, label):
        self.label = label
        self.calls = []
        self.closed = False

    def acquire(self):
        return FakeConn(self)

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return None

def test_mysql_database_routes_reads_and_writes(monkeypatch):
    async def scenario():
        created = []

        async def fake_create_pool(**kwargs):
            pool = FakePool(kwargs["host"])
            created.append(kwargs)
            return pool

        monkeypatch.setattr(
            MySQLDatabase,
            "_load_aiomysql",
            staticmethod(lambda: (SimpleNamespace(create_pool=fake_create_pool), object)),
        )

        db = MySQLDatabase(
            {
                "master": {
                    "host": "master-db",
                    "port": 3306,
                    "user": "writer",
                    "password": "secret",
                    "database": "demo",
                },
                "slaves": [
                    {"host": "slave-a", "port": 3306, "user": "writer", "password": "secret", "database": "demo"},
                    {"host": "slave-b", "port": 3306, "user": "writer", "password": "secret", "database": "demo"},
                ],
                "pool_size": 2,
                "pool_recycle": 1800,
            }
        )

        await db.connect()

        assert [item["host"] for item in created] == ["master-db", "slave-a", "slave-b"]

        first = await db.execute_one("SELECT 1", ())
        second = await db.execute_one("SELECT 2", ())
        inserted = await db.execute_insert("INSERT INTO demo(name) VALUES (%s)", ("alpha",))
        many = await db.execute_many("INSERT INTO demo(name) VALUES (%s)", [("beta",), ("gamma",)])

        assert first["pool"] == "slave-a"
        assert second["pool"] == "slave-b"
        assert inserted == 42
        assert many == 3
        assert db.master_pool.label == "master-db"
        assert db.read_pools[0].label == "slave-a"
        assert db.read_pools[1].label == "slave-b"

        await db.disconnect()

        assert db.master_pool is None
        assert db.read_pools == []

    asyncio.run(scenario())
