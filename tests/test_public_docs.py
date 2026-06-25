import asyncio

from framework.app import create_app


def test_public_docs_are_served_from_public_docs_directory():
    app = create_app()

    _, response = asyncio.run(app.asgi_client.get("/docs/index.md"))

    assert response.status == 200
    assert "Sanic Framework Docs" in response.text
