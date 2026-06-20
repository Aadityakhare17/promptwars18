"""Security integration tests for XSS, CSRF, Rate Limiting, and Size limits."""

from app.models import ChatRequest


def test_xss_sanitization():
    """Verify that dangerous script injections are escaped or stripped."""
    # Test script tags stripped/escaped
    req = ChatRequest(message="Hello <script>alert('xss')</script> world!")
    assert "<script>" not in req.message
    assert "alert" in req.message

    # Test event handler injection stripped/escaped
    req2 = ChatRequest(message="Hello <img src=x onerror=alert(1)>")
    assert "onerror=" not in req2.message


def test_csrf_protection_enforced(client):
    """Verify state-changing POST requests require valid CSRF cookies/headers."""
    # Attempt POST without CSRF headers
    payload = {"transport": [], "energy": [], "food": [], "waste": []}
    response = client.post("/api/carbon/calculate", json=payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF token missing"


def test_csrf_mismatched_token_rejected(client, csrf_tokens):
    """Verify mismatched CSRF header/cookie returns 403 Forbidden."""
    headers = {"x-csrf-token": "completely-wrong-token"}
    cookies = {"csrf_token": csrf_tokens["cookie"]}

    payload = {"transport": [], "energy": [], "food": [], "waste": []}
    response = client.post(
        "/api/carbon/calculate", json=payload, headers=headers, cookies=cookies
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF token mismatch"


def test_request_size_limiter():
    """Verify that payloads exceeding the 1MB limit receive a 413 Payload Too Large."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    local_app = create_app()
    local_client = TestClient(local_app)

    csrf_resp = local_client.get("/api/csrf-token")
    csrf_token = csrf_resp.json()["csrf_token"]
    csrf_cookie = csrf_resp.cookies.get("csrf_token")

    # Exceeds settings.max_request_body_bytes (1048576)
    headers = {
        "x-csrf-token": csrf_token,
        "Content-Length": "1048577",
    }
    cookies = {"csrf_token": csrf_cookie}

    response = local_client.post(
        "/api/carbon/calculate",
        data="x" * 1048577,
        headers=headers,
        cookies=cookies,
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "Request body too large"


def test_rate_limiter_active(client):
    """Verify the per-IP rate limiter triggers 429 after threshold exceeded."""
    # Rapidly call a read-only endpoint (which rate limits but exempts static files)
    # The health check is not exempt from rate limit middleware
    limit_exceeded = False

    # We send more requests than the limit (requests_per_minute is 30 by default)
    # Since health-check is cheap, we can request 35 times.
    for _ in range(35):
        response = client.get("/api/health")
        if response.status_code == 429:
            limit_exceeded = True
            break

    assert limit_exceeded is True


def test_hsts_and_secure_cookies():
    """Verify that HSTS header and secure cookies are set when using HTTPS."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    # Create a fresh app instance to reset rate limits
    local_app = create_app()
    local_client = TestClient(local_app)

    # Check HSTS on health endpoint
    response = local_client.get("/api/health")
    assert "Strict-Transport-Security" in response.headers
    assert response.headers["Strict-Transport-Security"] == (
        "max-age=31536000; includeSubDomains; preload"
    )

    # Fetch CSRF token over mock HTTPS (using header x-forwarded-proto = https)
    headers = {"x-forwarded-proto": "https"}
    response = local_client.get("/api/csrf-token", headers=headers)
    assert response.status_code == 200

    # Verify cookie secure flag
    cookies = response.headers.get("set-cookie", "")
    assert "secure" in cookies.lower()
    assert "samesite=strict" in cookies.lower()


def test_rate_limiter_x_forwarded_for():
    """Verify rate limiter extracts client IP from X-Forwarded-For header."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    local_app = create_app()
    local_client = TestClient(local_app)

    headers = {"x-forwarded-for": "203.0.113.195, 70.41.3.18"}
    response = local_client.get("/api/health", headers=headers)
    assert response.status_code == 200


def test_chat_rate_limiting():
    """Verify separate rate limiting for the chat endpoint."""
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from app.main import create_app

    # Mock settings.rate_limit.chat_requests_per_minute to 2 to trigger limit quickly
    from app.config import settings

    with patch.object(settings.rate_limit, "chat_requests_per_minute", 2):
        local_app_mocked = create_app()
        local_client_mocked = TestClient(local_app_mocked)

        csrf_resp_mocked = local_client_mocked.get("/api/csrf-token")
        csrf_token_mocked = csrf_resp_mocked.json()["csrf_token"]
        csrf_cookie_mocked = csrf_resp_mocked.cookies.get("csrf_token")

        headers_mocked = {
            "x-csrf-token": csrf_token_mocked,
        }
        cookies_mocked = {"csrf_token": csrf_cookie_mocked}

        # Mock chat response to avoid hitting LLM API
        with patch("app.routes.chat.get_chat_response") as mock_chat:
            from app.services.chat_service import ProviderResult

            mock_chat.return_value = ProviderResult(
                reply="Hi", provider="gemini", success=True
            )

            # Request 1 (Success)
            resp1 = local_client_mocked.post(
                "/api/chat",
                json={"message": "hi"},
                headers=headers_mocked,
                cookies=cookies_mocked,
            )
            assert resp1.status_code == 200

            # Request 2 (Success)
            resp2 = local_client_mocked.post(
                "/api/chat",
                json={"message": "hi"},
                headers=headers_mocked,
                cookies=cookies_mocked,
            )
            assert resp2.status_code == 200

            # Request 3 (Rate Limited - 429)
            resp3 = local_client_mocked.post(
                "/api/chat",
                json={"message": "hi"},
                headers=headers_mocked,
                cookies=cookies_mocked,
            )
            assert resp3.status_code == 429
            assert "Rate limit exceeded" in resp3.json()["detail"]


def test_middleware_static_bypass():
    """Verify that static files bypass rate limiting and csrf checks."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    local_app = create_app()
    local_client = TestClient(local_app)

    # Sending a POST request to static path (normally requires CSRF/Rate Limiting)
    # It should bypass and return 405 (Method Not Allowed)
    # rather than 403 (CSRF missing) or 429.
    response = local_client.post("/static/non_existent_file.js")
    assert response.status_code == 405
