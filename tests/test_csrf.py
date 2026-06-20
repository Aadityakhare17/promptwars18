"""Unit tests for CSRF protection middleware."""

from unittest.mock import MagicMock

import pytest
from fastapi import Request, Response

from app.security.csrf import (
    CSRFMiddleware,
    _constant_time_compare,
    generate_csrf_token,
)


def test_generate_csrf_token():
    """Verify csrf token generation."""
    token = generate_csrf_token()
    assert isinstance(token, str)
    assert len(token) == 64  # 32 bytes hex encoded


def test_constant_time_compare():
    """Verify comparison function matches and mismatches correctly."""
    assert _constant_time_compare("abc", "abc") is True
    assert _constant_time_compare("abc", "def") is False


@pytest.mark.asyncio
async def test_csrf_middleware_safe_method_sets_cookie():
    """Verify safe method request sets csrf cookie if not present."""
    middleware = CSRFMiddleware(app=None)

    # Mock request
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/some-safe-path"
    request.url.scheme = "http"
    request.headers = {}
    request.cookies = {}

    # Mock next handler
    response = MagicMock(spec=Response)
    response.headers = {}

    async def call_next(req):
        return response

    res = await middleware.dispatch(request, call_next)
    assert res is response
    response.set_cookie.assert_called_once()
    args, kwargs = response.set_cookie.call_args
    assert kwargs["key"] == "csrf_token"
    assert kwargs["httponly"] is False
    assert kwargs["samesite"] == "strict"


def test_csrf_middleware_exempt_path():
    """Verify that exempt paths bypass CSRF checks for unsafe methods."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    local_app = create_app()
    local_client = TestClient(local_app)

    # POST to /api/health (which only supports GET)
    # If CSRF is bypassed, it should return 405 Method Not Allowed
    # instead of 403 Forbidden.
    response = local_client.post("/api/health")
    assert response.status_code == 405
