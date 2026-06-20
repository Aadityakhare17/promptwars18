"""Unit tests for Google Analytics 4 service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.services.analytics import log_analytics_event


@pytest.mark.asyncio
async def test_log_analytics_simulator():
    """Verify event logged via simulator when configured."""
    with patch.object(settings.google, "auth_simulator_enabled", True):
        success = await log_analytics_event("client-123", "test_event", {"key": "val"})
        assert success is True


@pytest.mark.asyncio
async def test_log_analytics_real_success():
    """Verify event logged successfully via real client."""
    mock_resp = MagicMock()
    mock_resp.status_code = 204

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp

    with patch.object(settings.google, "auth_simulator_enabled", False):
        with patch.object(settings.google, "ga_measurement_id", "G-REAL123"):
            with patch(
                "app.services.analytics.get_http_client", return_value=mock_client
            ):
                success = await log_analytics_event(
                    "client-123", "test_event", {"key": "val"}
                )
                assert success is True
                mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_log_analytics_real_bad_status():
    """Verify log returns False when GA4 returns bad status code."""
    mock_resp = MagicMock()
    mock_resp.status_code = 400

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp

    with patch.object(settings.google, "auth_simulator_enabled", False):
        with patch.object(settings.google, "ga_measurement_id", "G-REAL123"):
            with patch(
                "app.services.analytics.get_http_client", return_value=mock_client
            ):
                success = await log_analytics_event(
                    "client-123", "test_event", {"key": "val"}
                )
                assert success is False


@pytest.mark.asyncio
async def test_log_analytics_exception():
    """Verify log returns False when client post raises exception."""
    mock_client = AsyncMock()
    mock_client.post.side_effect = Exception("Network failure")

    with patch.object(settings.google, "auth_simulator_enabled", False):
        with patch.object(settings.google, "ga_measurement_id", "G-REAL123"):
            with patch(
                "app.services.analytics.get_http_client", return_value=mock_client
            ):
                success = await log_analytics_event("client-123", "test_event")
                assert success is False
