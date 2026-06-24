import asyncio

from app.v1.model.demo import CatalogModel, OrderModel


class FakeRedis:
    def __init__(self):
        self.calls = []
        self.store = {}

    async def get(self, key):
        self.calls.append(("get", key))
        return self.store.get(key)

    async def setex(self, key, seconds, value):
        self.calls.append(("setex", key, seconds, value))
        self.store[key] = value
        return True

    async def delete(self, key):
        self.calls.append(("delete", key))
        self.store.pop(key, None)
        return 1


class FakeMySQL:
    def __init__(self):
        self.calls = []

    async def execute_one_master(self, query, args=None, request=None):
        self.calls.append(("execute_one_master", query, tuple(args or ())))
        return {"id": args[0], "name": "master-order"}

    async def execute_one(self, query, args=None, request=None):
        self.calls.append(("execute_one", query, tuple(args or ())))
        return {"id": args[0], "name": "auto-catalog"}

    async def execute_master(self, query, args=None, request=None):
        self.calls.append(("execute_master", query, tuple(args or ())))
        return [{"id": 1, "name": "master"}]

    async def execute(self, query, args=None, request=None):
        self.calls.append(("execute", query, tuple(args or ())))
        return [{"id": 1, "name": "slave"}]

    async def execute_insert(self, query, args=None, request=None):
        self.calls.append(("execute_insert", query, tuple(args or ())))
        return 11

    async def execute_update(self, query, args=None, request=None):
        self.calls.append(("execute_update", query, tuple(args or ())))
        return 1


class FakeAppCtx:
    def __init__(self, mysql, redis):
        self.mysql = mysql
        self.redis = redis


class FakeApp:
    def __init__(self, mysql, redis):
        self.ctx = FakeAppCtx(mysql, redis)


class FakeRequest:
    def __init__(self, mysql, redis):
        self.app = FakeApp(mysql, redis)


def test_legacy_model_demo_keeps_old_style_and_master_default():
    async def scenario():
        mysql = FakeMySQL()
        redis = FakeRedis()
        request = FakeRequest(mysql, redis)

        order = OrderModel(request)
        catalog = CatalogModel(request)

        order_row = await order.get_one(1001)
        catalog_rows = await catalog.get_all()
        inserted = await order.insert(id=1001, amount=12.5)
        updated = await order.update(1001, amount=18.0)

        assert order_row["name"] == "master-order"
        assert catalog_rows[0]["name"] == "slave"
        assert inserted == 11
        assert updated == 1

        assert ("execute_one_master", "SELECT * FROM `orders` WHERE `id` = %s LIMIT %s", (1001, 1)) in mysql.calls
        assert any(
            call[0] == "execute"
            and "FROM `catalog`" in call[1]
            and "`data_state` = %s" in call[1]
            for call in mysql.calls
        )
        assert any(call[0] == "execute_update" for call in mysql.calls)

    asyncio.run(scenario())
