"""Google Cloud Storage service.

Uploads carbon footprint calculations and history to GCS.
Provides a mock simulation mode for local developer testing when credentials are absent.
"""

import json
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# Try to import Google Cloud Storage libraries, fallback to mock if missing
try:
    from google.cloud import storage

    _GCS_AVAILABLE = True
except ImportError:
    _GCS_AVAILABLE = False
    logger.warning(
        "Google Cloud Storage client libraries not installed. "
        "Using simulation mode."
    )


class GCSService:
    """Service to manage Google Cloud Storage integration."""

    def __init__(self) -> None:
        """Initialize GCS client if configured, else prepare mock storage."""
        self.bucket_name = settings.google.gcs_bucket_name
        self.simulator = settings.google.auth_simulator_enabled
        self.client = None

        if not self.simulator and _GCS_AVAILABLE:
            try:
                # Check if credentials are set up
                if settings.google.google_client_id != "YOUR_GOOGLE_CLIENT_ID_HERE":
                    self.client = storage.Client()
                    logger.info("Google Cloud Storage client initialized successfully.")
            except Exception as exc:
                logger.error(
                    "Failed to initialize GCS client: %s. Falling back to simulation.",
                    exc,
                )

    async def upload_json(self, blob_name: str, data: dict[str, Any]) -> bool:
        """Upload JSON data to a GCS bucket.

        Args:
            blob_name: Name of the blob/file in GCS.
            data: Dictionary content to upload.

        Returns:
            True if upload succeeded or simulation mode was active.
        """
        payload_str = json.dumps(data, indent=2)

        if self.simulator or not self.client:
            # Simulation / Developer Bypass mode
            logger.info(
                "[GCS SIMULATOR] Uploading blob '%s' to bucket '%s' with content: %s",
                blob_name,
                self.bucket_name,
                payload_str[:150] + "...",
            )
            return True

        # Real GCS upload logic
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_name)
            blob.upload_from_string(payload_str, content_type="application/json")
            logger.info(
                "Successfully uploaded blob '%s' to GCS bucket '%s'",
                blob_name,
                self.bucket_name,
            )
            return True
        except Exception as exc:
            logger.error(
                "GCS upload failed for blob '%s' in bucket '%s': %s",
                blob_name,
                self.bucket_name,
                exc,
            )
            return False


# Singleton instance
gcs_service = GCSService()
