"""Unit tests for main application endpoints and middleware."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Response


def test_serve_index(client):
    """Verify that GET / returns index.html content with no-cache headers."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert response.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"


def test_serve_static_files(client):
    """Verify that static files are served with public caching headers."""
    # We request the app.js file
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
    assert "Cache-Control" in response.headers
    assert "public, max-age=" in response.headers["Cache-Control"]


def test_get_analytics_config(client):
    """Verify that analytics config returns correct values."""
    response = client.get("/api/analytics/config")
    assert response.status_code == 200
    data = response.json()
    assert "ga_measurement_id" in data
    assert "simulator_enabled" in data


def test_remove_headers_middleware():
    """Verify that Server and X-Powered-By headers are removed by middleware."""
    from app.main import SecurityHeadersMiddleware

    # We mock the call_next handler to return headers we want removed
    async def mock_call_next(request):
        res = Response()
        res.headers["Server"] = "uvicorn"
        res.headers["X-Powered-By"] = "Python"
        return res

    middleware = SecurityHeadersMiddleware(app=None)

    # Run the middleware dispatch
    mock_request = AsyncMock()
    import asyncio

    loop = asyncio.get_event_loop()
    response = loop.run_until_complete(
        middleware.dispatch(mock_request, mock_call_next)
    )

    assert "Server" not in response.headers
    assert "X-Powered-By" not in response.headers


@pytest.mark.asyncio
async def test_shutdown_event():
    """Verify shutdown event triggers closing the global HTTP client."""
    from app.main import create_app

    app = create_app()
    with patch("app.main.close_http_client", new_callable=AsyncMock) as mock_close:
        # Manually trigger registered shutdown events on app router
        for handler in app.router.on_shutdown:
            await handler()
        mock_close.assert_called_once()
