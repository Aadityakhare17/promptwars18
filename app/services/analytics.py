"""Google Analytics 4 Measurement Protocol integration.

Provides helper methods to log server-side analytics events to GA4.
"""

import logging

from app.config import settings
from app.services.http_client import get_http_client

logger = logging.getLogger(__name__)


async def log_analytics_event(
    client_id: str, event_name: str, params: dict = None
) -> bool:
    """Send a server-side analytics event to Google Analytics 4.

    Args:
        client_id: Unique client identifier (e.g., session ID).
        event_name: Name of the event (e.g., 'carbon_calculated').
        params: Key-value parameters for the event.

    Returns:
        True if the event was successfully dispatched or simulated.
    """
    if params is None:
        params = {}

    measurement_id = settings.google.ga_measurement_id

    if settings.google.auth_simulator_enabled or measurement_id == "G-MOCKMEASUREID":
        logger.info(
            "[ANALYTICS SIMULATOR] Event: '%s', Client: '%s', Params: %s",
            event_name,
            client_id,
            params,
        )
        return True

    # Real GA4 Measurement Protocol call
    # API secret can be empty or simulated for simple event validation
    url = f"https://www.google-analytics.com/mp/collect?measurement_id={measurement_id}"
    payload = {
        "client_id": client_id,
        "events": [{"name": event_name, "params": params}],
    }

    try:
        client = get_http_client()
        response = await client.post(url, json=payload)
        if response.status_code in (200, 204):
            logger.info("Successfully sent analytics event '%s' to GA4", event_name)
            return True
        logger.warning(
            "Failed to send GA4 event '%s', status: %s",
            event_name,
            response.status_code,
        )
        return False
    except Exception as exc:
        logger.error("Error sending GA4 event: %s", exc)
        return False
