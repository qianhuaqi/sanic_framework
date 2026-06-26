import asyncio

from lingshu.app import create_app


def test_cors_headers_are_added_when_enabled(monkeypatch):
    monkeypatch.setenv("CORS_ENABLED", "true")
    monkeypatch.setenv("CORS_ORIGINS", "https://client.test")
    monkeypatch.setenv("CORS_ALLOW_METHODS", "GET,POST,OPTIONS")
    monkeypatch.setenv("CORS_ALLOW_HEADERS", "Content-Type,Authorization")

    async def scenario():
        app = create_app()
        _, response = await app.asgi_client.get("/health", headers={"Origin": "https://client.test"})

        assert response.status == 200
        assert response.headers["access-control-allow-origin"] == "https://client.test"
        assert response.headers["access-control-allow-methods"] == "GET, POST, OPTIONS"
        assert response.headers["access-control-allow-headers"] == "Content-Type, Authorization"

    asyncio.run(scenario())


def test_cors_preflight_is_handled_by_framework(monkeypatch):
    monkeypatch.setenv("CORS_ENABLED", "true")
    monkeypatch.setenv("CORS_ORIGINS", "*")

    async def scenario():
        app = create_app()
        _, response = await app.asgi_client.options(
            "/v1/demo",
            headers={
                "Origin": "https://client.test",
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.status == 204
        assert response.headers["access-control-allow-origin"] == "*"

    asyncio.run(scenario())
