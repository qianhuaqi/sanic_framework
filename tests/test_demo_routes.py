import asyncio

from framework.app import create_app
from app.v1.controller import demo as demo_controller


class DummyDB:
    pass


class DummyRedis:
    pass


class FakeDemoModel:
    def __init__(self, request):
        self.request = request

    async def get_pagination(self, page=1, size=10, data_id=0, order_by=None, use_master=None, **kwargs):
        return {"items": [{"id": 1, "name": "demo"}], "page": page, "per_page": size, "total": 1, "pages": 1}

    async def get_one(self, data_id, fields=None, use_master=None, use_cache=True):
        return {"id": str(data_id), "name": "demo-row", "use_cache": use_cache}

    async def insert(self, **kwargs):
        return 9

    async def update(self, data_id, **kwargs):
        return 1

    async def delete(self, data_id, physical=False):
        return 1


def test_demo_routes_expose_table_crud_endpoints(monkeypatch):
    monkeypatch.setattr(demo_controller, "DemoModel", FakeDemoModel)

    async def scenario():
        app = create_app()
        app.ctx.mysql = DummyDB()
        app.ctx.redis = DummyRedis()

        _, index_response = await app.asgi_client.get("/v1/demo?page=2&size=5")
        _, info_response = await app.asgi_client.get("/v1/demo/7?use_cache=1")
        _, add_response = await app.asgi_client.post("/v1/demo", json={"name": "created"})
        _, edit_response = await app.asgi_client.put("/v1/demo/7", json={"name": "updated"})
        _, patch_response = await app.asgi_client.patch("/v1/demo/7", json={"name": "patched"})
        _, del_response = await app.asgi_client.delete("/v1/demo/7")
        _, legacy_response = await app.asgi_client.get("/demo/index?page=1&size=2")

        assert index_response.status == 200
        assert index_response.json["data"]["items"][0]["name"] == "demo"
        assert index_response.json["data"]["page"] == 2

        assert info_response.status == 200
        assert info_response.json["data"]["id"] == "7"
        assert info_response.json["data"]["use_cache"] is True

        assert add_response.status == 201
        assert add_response.json["data"]["id"] == 9

        assert edit_response.status == 200
        assert edit_response.json["data"]["updated"] == 1

        assert patch_response.status == 200
        assert patch_response.json["data"]["updated"] == 1

        assert del_response.status == 200
        assert del_response.json["data"]["deleted"] == 1

        assert legacy_response.status == 404

    asyncio.run(scenario())
