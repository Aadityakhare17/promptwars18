"""Unit tests for Google Cloud Storage service."""

from unittest.mock import MagicMock, patch

import pytest

from app.config import settings
from app.services.gcs_service import GCSService


def test_gcs_init_simulator():
    """Verify GCSService initializes in simulator mode when configured."""
    with patch.object(settings.google, "auth_simulator_enabled", True):
        service = GCSService()
        assert service.simulator is True
        assert service.client is None


def test_gcs_init_real_success():
    """Verify GCSService initializes storage client when simulator is disabled."""
    mock_client = MagicMock()
    with patch.object(settings.google, "auth_simulator_enabled", False):
        with patch.object(settings.google, "google_client_id", "real-client-id"):
            with patch("google.cloud.storage.Client", return_value=mock_client):
                service = GCSService()
                assert service.simulator is False
                assert service.client is mock_client


def test_gcs_init_real_failure():
    """Verify GCS initialization failure falls back gracefully."""
    with patch.object(settings.google, "auth_simulator_enabled", False):
        with patch.object(settings.google, "google_client_id", "real-client-id"):
            with patch(
                "google.cloud.storage.Client", side_effect=Exception("Auth error")
            ):
                service = GCSService()
                assert service.client is None


@pytest.mark.asyncio
async def test_gcs_upload_simulator():
    """Verify JSON upload succeeds via simulation."""
    with patch.object(settings.google, "auth_simulator_enabled", True):
        service = GCSService()
        success = await service.upload_json("test_blob.json", {"key": "value"})
        assert success is True


@pytest.mark.asyncio
async def test_gcs_upload_real_success():
    """Verify JSON upload succeeds with real GCS client mocked."""
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    with patch.object(settings.google, "auth_simulator_enabled", False):
        with patch.object(settings.google, "google_client_id", "real-client-id"):
            with patch("google.cloud.storage.Client", return_value=mock_client):
                service = GCSService()
                success = await service.upload_json("test_blob.json", {"key": "value"})
                assert success is True
                mock_client.bucket.assert_called_once_with(service.bucket_name)
                mock_bucket.blob.assert_called_once_with("test_blob.json")
                mock_blob.upload_from_string.assert_called_once()


@pytest.mark.asyncio
async def test_gcs_upload_real_failure():
    """Verify JSON upload returns False when an exception is raised by GCS client."""
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_blob.upload_from_string.side_effect = Exception("Upload timed out")

    with patch.object(settings.google, "auth_simulator_enabled", False):
        with patch.object(settings.google, "google_client_id", "real-client-id"):
            with patch("google.cloud.storage.Client", return_value=mock_client):
                service = GCSService()
                success = await service.upload_json("test_blob.json", {"key": "value"})
                assert success is False


def test_gcs_library_import_error():
    """Verify fallback behavior when google-cloud-storage is not installed."""
    import sys

    # Keep a reference to restore later
    old_mod = sys.modules.get("app.services.gcs_service")

    with patch.dict(sys.modules, {"google.cloud": None, "google.cloud.storage": None}):
        if "app.services.gcs_service" in sys.modules:
            del sys.modules["app.services.gcs_service"]

        import app.services.gcs_service as gcs_service_mod

        assert gcs_service_mod._GCS_AVAILABLE is False

    # Restore the original module state
    if old_mod:
        sys.modules["app.services.gcs_service"] = old_mod
    else:
        if "app.services.gcs_service" in sys.modules:
            del sys.modules["app.services.gcs_service"]
