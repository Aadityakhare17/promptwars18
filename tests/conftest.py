"""Pytest configuration and shared fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a TestClient for sync requests."""
    return TestClient(app)


@pytest.fixture
def csrf_tokens(client):
    """Retrieve a valid CSRF token and cookie for testing."""
    response = client.get("/api/csrf-token")
    assert response.status_code == 200
    data = response.json()
    token = data["csrf_token"]
    cookie = response.cookies.get("csrf_token")
    return {"token": token, "cookie": cookie}
