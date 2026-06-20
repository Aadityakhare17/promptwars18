"""Unit and integration tests for authentication routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings


def test_google_login_simulator_enabled(client):
    """Verify login redirect when simulator is enabled."""
    with patch.object(settings.google, "auth_simulator_enabled", True):
        # We follow redirects = False to check the Location header
        response = client.get("/api/auth/google/login", follow_redirects=False)
        assert response.status_code == 307
        assert (
            "api/auth/google/callback?code=mock_code_12345"
            in response.headers["location"]
        )


def test_google_login_simulator_disabled_not_configured(client):
    """Verify 400 error when simulator is disabled but client ID is placeholder."""
    with patch.object(settings.google, "auth_simulator_enabled", False):
        with patch.object(
            settings.google, "google_client_id", "YOUR_GOOGLE_CLIENT_ID_HERE"
        ):
            response = client.get("/api/auth/google/login")
            assert response.status_code == 400
            assert "Google Client ID is not configured" in response.json()["detail"]


def test_google_login_simulator_disabled_configured(client):
    """Verify redirect to Google Auth screen when properly configured."""
    with patch.object(settings.google, "auth_simulator_enabled", False):
        with patch.object(settings.google, "google_client_id", "real-client-id"):
            response = client.get("/api/auth/google/login", follow_redirects=False)
            assert response.status_code == 307
            loc = response.headers["location"]
            assert "accounts.google.com" in loc
            assert "client_id=real-client-id" in loc


@pytest.mark.asyncio
async def test_google_callback_simulator(client):
    """Verify session cookie creation and redirection in callback simulator."""
    with patch.object(settings.google, "auth_simulator_enabled", True):
        response = client.get(
            "/api/auth/google/callback?code=mock_code_12345", follow_redirects=False
        )
        assert response.status_code == 307
        assert response.headers["location"] == "/"
        assert "auth_session" in response.cookies


@pytest.mark.asyncio
async def test_google_callback_real_success():
    """Verify successful Google token exchange and callback handling."""
    from app.main import create_app

    local_app = create_app()
    local_client = TestClient(local_app)

    mock_token_resp = MagicMock()
    mock_token_resp.status_code = 200
    mock_token_resp.json.return_value = {"access_token": "mock-access-token"}

    mock_userinfo_resp = MagicMock()
    mock_userinfo_resp.status_code = 200
    mock_userinfo_resp.json.return_value = {
        "name": "Jane Real",
        "email": "jane.real@gmail.com",
        "picture": "https://lh3.googleusercontent.com/pic",
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_token_resp
    mock_client.get.return_value = mock_userinfo_resp

    with patch.object(settings.google, "auth_simulator_enabled", False):
        with patch.object(settings.google, "google_client_id", "real-client-id"):
            with patch.object(settings.google, "google_client_secret", "real-secret"):
                with patch("app.routes.auth.get_http_client", return_value=mock_client):
                    response = local_client.get(
                        "/api/auth/google/callback?code=real_code",
                        follow_redirects=False,
                    )
                    assert response.status_code == 307
                    assert response.headers["location"] == "/"
                    assert "auth_session" in response.cookies

                    # Fetch user info with the session cookie set
                    user_resp = local_client.get(
                        "/api/auth/user", cookies=response.cookies
                    )
                    assert user_resp.status_code == 200
                    user_data = user_resp.json()
                    assert user_data["authenticated"] is True
                    assert user_data["user"]["name"] == "Jane Real"
                    assert user_data["user"]["email"] == "jane.real@gmail.com"


@pytest.mark.asyncio
async def test_google_callback_real_token_fail():
    """Verify error handled when token exchange fails."""
    from app.main import create_app

    local_app = create_app()
    local_client = TestClient(local_app)

    mock_token_resp = MagicMock()
    mock_token_resp.status_code = 400
    mock_token_resp.text = "invalid grant"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_token_resp

    with patch.object(settings.google, "auth_simulator_enabled", False):
        with patch.object(settings.google, "google_client_id", "real-client-id"):
            with patch("app.routes.auth.get_http_client", return_value=mock_client):
                response = local_client.get("/api/auth/google/callback?code=real_code")
                assert response.status_code == 500
                assert (
                    "An error occurred during authentication"
                    in response.json()["detail"]
                )


@pytest.mark.asyncio
async def test_google_callback_real_userinfo_fail():
    """Verify error handled when fetching user profile details fails."""
    from app.main import create_app

    local_app = create_app()
    local_client = TestClient(local_app)

    mock_token_resp = MagicMock()
    mock_token_resp.status_code = 200
    mock_token_resp.json.return_value = {"access_token": "mock-access-token"}

    mock_userinfo_resp = MagicMock()
    mock_userinfo_resp.status_code = 401

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_token_resp
    mock_client.get.return_value = mock_userinfo_resp

    with patch.object(settings.google, "auth_simulator_enabled", False):
        with patch.object(settings.google, "google_client_id", "real-client-id"):
            with patch("app.routes.auth.get_http_client", return_value=mock_client):
                response = local_client.get("/api/auth/google/callback?code=real_code")
                assert response.status_code == 500
                assert (
                    "An error occurred during authentication"
                    in response.json()["detail"]
                )


def test_get_user_unauthenticated(client):
    """Verify get user returns authenticated=False when no session cookie is present."""
    response = client.get("/api/auth/user")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "user": None}


def test_logout(client):
    """Verify logout clears cookie and active session."""
    with patch.object(settings.google, "auth_simulator_enabled", True):
        # 1. Login
        login_response = client.get(
            "/api/auth/google/callback?code=mock_code_12345", follow_redirects=False
        )
        cookies = login_response.cookies
        assert "auth_session" in cookies

        # 2. Get user (should be Jane Doe)
        user_response = client.get("/api/auth/user", cookies=cookies)
        assert user_response.json()["authenticated"] is True

        # 3. CSRF token for state-changing POST logout
        csrf_response = client.get("/api/csrf-token")
        csrf_token = csrf_response.json()["csrf_token"]
        csrf_cookie = csrf_response.cookies.get("csrf_token")

        # 4. Logout
        logout_headers = {"x-csrf-token": csrf_token}
        logout_cookies = {
            "csrf_token": csrf_cookie,
            "auth_session": cookies["auth_session"],
        }
        logout_response = client.post(
            "/api/auth/logout", headers=logout_headers, cookies=logout_cookies
        )
        assert logout_response.status_code == 200
        assert logout_response.json() == {"status": "logged_out"}

        # 5. Verify user is now unauthenticated
        verify_response = client.get("/api/auth/user", cookies=logout_cookies)
        assert verify_response.json()["authenticated"] is False
