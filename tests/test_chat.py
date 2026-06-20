"""Unit and integration tests for AI chatbot fallback chain."""

from unittest.mock import MagicMock, patch

import pytest

from app.config import settings
from app.services.chat_service import get_chat_response


@pytest.fixture(autouse=True)
def override_api_keys():
    """Ensure API keys are set to non-placeholder values for test matching."""
    with (
        patch.object(settings.ai, "gemini_api_key", "test_gemini_key"),
        patch.object(settings.ai, "claude_api_key", "test_claude_key"),
        patch.object(settings.ai, "chatgpt_api_key", "test_chatgpt_key"),
        patch.object(settings.ai, "perplexity_api_key", "test_perplexity_key"),
        patch.object(settings.ai, "deepseek_api_key", "test_deepseek_key"),
    ):
        yield


@pytest.mark.asyncio
async def test_chat_gemini_success():
    """Verify Gemini success is returned immediately without calling fallbacks."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Gemini response text"}]}}]
    }

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        result = await get_chat_response("Hello")
        assert result.success is True
        assert result.reply == "Gemini response text"
        assert result.provider == "gemini"
        # Verify it only made 1 API call (did not fallback)
        assert mock_post.call_count == 1


@pytest.mark.asyncio
async def test_chat_gemini_fails_falls_back_to_claude():
    """Verify Gemini failure triggers fallback to Claude."""
    # First call fails (Gemini), second call succeeds (Claude)
    mock_gemini_fail = MagicMock()
    mock_gemini_fail.status_code = 429
    mock_gemini_fail.text = "Rate limit exceeded"

    mock_claude_success = MagicMock()
    mock_claude_success.status_code = 200
    mock_claude_success.json.return_value = {
        "content": [{"type": "text", "text": "Claude response text"}]
    }

    responses = [mock_gemini_fail, mock_claude_success]

    with patch("httpx.AsyncClient.post", side_effect=responses) as mock_post:
        result = await get_chat_response("Hello")
        assert result.success is True
        assert result.reply == "Claude response text"
        assert result.provider == "claude"
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_chat_gemini_and_claude_fail_falls_back_to_chatgpt():
    """Verify Gemini and Claude failures trigger fallback to ChatGPT."""
    mock_gemini_fail = MagicMock()
    mock_gemini_fail.status_code = 500
    mock_gemini_fail.text = "Internal error"

    mock_claude_fail = MagicMock()
    mock_claude_fail.status_code = 429
    mock_claude_fail.text = "Token limit exceeded"

    mock_chatgpt_success = MagicMock()
    mock_chatgpt_success.status_code = 200
    mock_chatgpt_success.json.return_value = {
        "choices": [{"message": {"content": "ChatGPT response text"}}]
    }

    responses = [mock_gemini_fail, mock_claude_fail, mock_chatgpt_success]

    with patch("httpx.AsyncClient.post", side_effect=responses) as mock_post:
        result = await get_chat_response("Hello")
        assert result.success is True
        assert result.reply == "ChatGPT response text"
        assert result.provider == "chatgpt"
        assert mock_post.call_count == 3


@pytest.mark.asyncio
async def test_chat_all_fail_graceful_error():
    """Verify system handles all model failures gracefully without crashing."""
    mock_fail = MagicMock()
    mock_fail.status_code = 500
    mock_fail.text = "Service Unavailable"

    with patch("httpx.AsyncClient.post", return_value=mock_fail) as mock_post:
        result = await get_chat_response("Hello")
        assert result.success is True
        assert "offline mode" in result.reply
        assert result.provider == "local_knowledge_base"
        # Attempted all 5 models in the chain
        assert mock_post.call_count == 5


def test_api_chat_route_integration(client, csrf_tokens):
    """Verify chat route input validation and fallback API integration."""
    headers = {"x-csrf-token": csrf_tokens["token"]}
    cookies = {"csrf_token": csrf_tokens["cookie"]}

    # Mock success for Gemini to keep test simple
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Gemini response text"}]}}]
    }

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        response = client.post(
            "/api/chat",
            json={"message": "What is carbon footprint?"},
            headers=headers,
            cookies=cookies,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["reply"] == "Gemini response text"
        assert data["provider"] == "gemini"
        assert data["fallback_used"] is False


@pytest.mark.asyncio
async def test_chat_simulator_mode_when_keys_are_placeholders():
    """Verify chatbot returns simulated responses when keys are placeholders

    and simulator is enabled.
    """
    with (
        patch.object(settings.ai, "gemini_api_key", "YOUR_GEMINI_API_KEY_HERE"),
        patch.object(settings.google, "auth_simulator_enabled", True),
    ):
        result = await get_chat_response("How can I reduce my car emissions?")
        assert result.success is True
        assert result.provider == "gemini"
        assert "simulated" in result.reply.lower() or "gemini" in result.reply.lower()
        assert "car" in result.reply.lower() or "transit" in result.reply.lower()


@pytest.mark.asyncio
async def test_http_client_shutdown():
    """Verify the global HTTPX client can be initialized and shutdown cleanly."""
    from app.services.http_client import close_http_client, get_http_client

    client = get_http_client()
    assert client is not None
    await close_http_client()
    # verify the global variable is set to None on shutdown
    from app.services.http_client import _client

    assert _client is None
