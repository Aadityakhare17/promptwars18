"""Shared HTTPX client with connection pooling and limits.

Implements a single, reused global client to eliminate TCP/TLS handshake overhead
and dramatically improve network efficiency across LLM, Google OAuth, and GA4 requests.
"""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Reused global HTTPX client instance
_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    """Return the shared global httpx.AsyncClient instance.

    Configured with connection pooling limits to optimize concurrent requests.

    Returns:
        Shared httpx.AsyncClient instance.
    """
    global _client
    if _client is None:
        limits = httpx.Limits(
            max_keepalive_connections=10,
            max_connections=50,
        )
        # Reuses client with pooled connections and setting-defined timeouts
        _client = httpx.AsyncClient(
            limits=limits,
            timeout=httpx.Timeout(float(settings.ai.request_timeout_seconds)),
        )
        logger.info("Shared global HTTPX AsyncClient initialized.")
    return _client


async def close_http_client() -> None:
    """Gracefully close the global httpx.AsyncClient connection pool."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("Shared global HTTPX AsyncClient shutdown successfully.")
