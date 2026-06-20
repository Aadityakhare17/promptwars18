"""Unit tests for Pydantic models and field validators."""

import pytest
from pydantic import ValidationError

from app.models import CarbonEntry, ChatRequest, TransportEntry


def test_sanitize_text_long():
    """Verify text is truncated to maximum allowed length."""
    from app.models import _sanitize_text

    long_msg = "a" * 2500
    sanitized = _sanitize_text(long_msg)
    assert len(sanitized) == 2000


def test_validate_list_length_excessive():
    """Verify CarbonEntry raises validation error if category lists exceed 50 items."""
    # Create list of 51 entries
    excessive_transport = [TransportEntry(mode="car_petrol", distance_km=10)] * 51
    with pytest.raises(ValidationError) as exc_info:
        CarbonEntry(transport=excessive_transport)
    assert "Maximum 50 entries per category" in str(exc_info.value)


def test_session_id_invalid():
    """Verify session_id validator rejects non-alphanumeric/dash/underscore
    characters.
    """
    with pytest.raises(ValidationError) as exc_info:
        ChatRequest(message="hello", session_id="invalid/session/id")
    assert "Session ID must be alphanumeric" in str(exc_info.value)


def test_session_id_valid():
    """Verify session_id validator allows valid session IDs and None."""
    # None session ID
    req1 = ChatRequest(message="hello", session_id=None)
    assert req1.session_id is None

    # Valid session ID
    req2 = ChatRequest(message="hello", session_id="session_123-abc_xyz")
    assert req2.session_id == "session_123-abc_xyz"
