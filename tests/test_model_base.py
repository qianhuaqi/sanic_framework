import asyncio
import json

from lingshu.model.base import BaseModel


class FakeDB:
    def __init__(self):
        self.calls = []

    async def execute(self, query, args=None, request=None):
        self.calls.append(("execute", query, tuple(args or ())))
        return [{"id": 1, "name": "alpha"}]

    async def execute_one(self, query, args=None, request=None):
        self.calls.append(("execute_one", query, tuple(args or ())))
        if "COUNT(*)" in query:
            return {"count": 2}
        pk = (args or [1])[0]
        return {"id": pk, "name": f"article-{pk}"}

    async def execute_insert(self, query, args=None, request=None):
        self.calls.append(("execute_insert", query, tuple(args or ())))
        return 7

    async def execute_update(self, query, args=None, request=None):
        self.calls.append(("execute_update", query, tuple(args or ())))
        return 1

    async def execute_many(self, query, args_list, request=None):
        self.calls.append(("execute_many", query, tuple(args_list)))
        return len(args_list)


class FakeRedis:
    def __init__(self):
        self.calls = []
        self.store = {}

    async def get(self, key):
        self.calls.append(("get", key))
        return self.store.get(key)

    async def set(self, key, value):
        self.calls.append(("set", key, value))
        self.store[key] = value
        return True

    async def setex(self, key, seconds, value):
        self.calls.append(("setex", key, seconds, value))
        self.store[key] = value
        return True

    async def delete(self, key):
        self.calls.append(("delete", key))
        self.store.pop(key, None)
        return 1


class ArticleModel(BaseModel):
    table_name = "articles"
    fillable = ("title", "body", "status")
    default_order_by = ("`id` DESC",)
    cache_enabled = True

def test_base_model_builds_common_queries():
    async def scenario():
        db = FakeDB()

        row = await ArticleModel.find_by_pk(db, 1)
        listed = await ArticleModel.find_all(db, filters={"status": "published"}, limit=10)
        count = await ArticleModel.count(db, filters={"status": "published"})
        inserted = await ArticleModel.insert(db, {"title": "hello", "body": "world", "id": 99})
        updated = await ArticleModel.update(db, {"title": "changed", "id": 88}, pk=1)
        deleted = await ArticleModel.delete(db, pk=1)
        paginated = await ArticleModel.paginate(db, page=2, per_page=5)

        assert row["id"] == 1
        assert listed[0]["name"] == "alpha"
        assert count == 2
        assert inserted == 7
        assert updated == 1
        assert deleted == 1
        assert paginated["page"] == 2
        assert paginated["per_page"] == 5
        assert paginated["total"] == 2
        assert paginated["pages"] == 1

        execute_insert_sql = next(query for kind, query, _ in db.calls if kind == "execute_insert")
        assert "INSERT INTO `articles`" in execute_insert_sql
        assert "`id`" not in execute_insert_sql

        update_call = next(item for item in db.calls if item[0] == "execute_update")
        assert "UPDATE `articles` SET" in update_call[1]
        assert update_call[2][-1] == 1

    asyncio.run(scenario())


def test_base_model_uses_cache_for_primary_key_reads():
    async def scenario():
        db = FakeDB()
        redis = FakeRedis()
        redis.store["model:articles:1"] = json.dumps({"id": 1, "name": "cached"})

        row = await ArticleModel.find_by_pk(db, 1, redis=redis, use_cache=True)
        miss = await ArticleModel.find_by_pk(db, 2, redis=redis, use_cache=True)

        assert row == {"id": 1, "name": "cached"}
        assert miss == {"id": 2, "name": "article-2"}
        assert db.calls == [
            ("execute_one", "SELECT * FROM `articles` WHERE `id` = %s ORDER BY `id` DESC LIMIT %s", (2, 1))
        ]
        assert redis.calls == [
            ("get", "model:articles:1"),
            ("get", "model:articles:2"),
            ("setex", "model:articles:2", 300, '{"id": 2, "name": "article-2"}'),
        ]

    asyncio.run(scenario())


def test_base_model_can_bypass_cache_when_requested():
    async def scenario():
        db = FakeDB()
        redis = FakeRedis()
        redis.store["model:articles:1"] = json.dumps({"id": 1, "name": "cached"})

        row = await ArticleModel.find_by_pk(db, 1, redis=redis, use_cache=False)

        assert row["id"] == 1
        assert db.calls and db.calls[0][0] == "execute_one"
        assert redis.calls == []

    asyncio.run(scenario())


def test_base_model_invalidates_cache_on_update_and_delete():
    async def scenario():
        db = FakeDB()
        redis = FakeRedis()
        redis.store["model:articles:1"] = json.dumps({"id": 1, "name": "cached"})

        await ArticleModel.update(db, {"title": "changed"}, pk=1, redis=redis)
        assert redis.store.get("model:articles:1") is None
        assert ("delete", "model:articles:1") in redis.calls

        redis.store["model:articles:1"] = json.dumps({"id": 1, "name": "cached"})
        redis.calls.clear()
        await ArticleModel.delete(db, pk=1, redis=redis)
        assert redis.store.get("model:articles:1") is None
        assert ("delete", "model:articles:1") in redis.calls

    asyncio.run(scenario())
