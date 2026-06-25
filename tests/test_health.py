import asyncio

from framework.app import create_app


def test_health_endpoint_without_databases():
    app = create_app()

    _, response = asyncio.run(app.asgi_client.get("/health"))

    assert response.status == 200
    assert response.json["code"] == 0
    assert response.json["msg"] == "ok"
    assert response.json["data"]["status"] == "ok"
