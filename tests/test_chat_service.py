"""Unit tests for chat service simulated responses and fallbacks."""

from unittest.mock import MagicMock, patch

import pytest

from app.config import settings
from app.services.chat_service import get_chat_response


@pytest.mark.asyncio
async def test_chat_simulator_diet():
    """Verify simulated response for diet queries."""
    with (
        patch.object(settings.ai, "gemini_api_key", "YOUR_GEMINI_API_KEY_HERE"),
        patch.object(settings.google, "auth_simulator_enabled", True),
    ):
        result = await get_chat_response("What food should I eat?")
        assert result.success is True
        assert "diet" in result.reply.lower() or "meat" in result.reply.lower()


@pytest.mark.asyncio
async def test_chat_simulator_energy():
    """Verify simulated response for energy queries."""
    with (
        patch.object(settings.ai, "gemini_api_key", "YOUR_GEMINI_API_KEY_HERE"),
        patch.object(settings.google, "auth_simulator_enabled", True),
    ):
        result = await get_chat_response("How to save electricity?")
        assert result.success is True
        assert (
            "energy" in result.reply.lower()
            or "solar" in result.reply.lower()
            or "electricity" in result.reply.lower()
        )


@pytest.mark.asyncio
async def test_chat_simulator_waste():
    """Verify simulated response for waste queries."""
    with (
        patch.object(settings.ai, "gemini_api_key", "YOUR_GEMINI_API_KEY_HERE"),
        patch.object(settings.google, "auth_simulator_enabled", True),
    ):
        result = await get_chat_response("Should I recycle plastic trash?")
        assert result.success is True
        assert (
            "waste" in result.reply.lower()
            or "recycle" in result.reply.lower()
            or "plastic" in result.reply.lower()
        )


@pytest.mark.asyncio
async def test_chat_simulator_offsets():
    """Verify simulated response for offset queries."""
    with (
        patch.object(settings.ai, "gemini_api_key", "YOUR_GEMINI_API_KEY_HERE"),
        patch.object(settings.google, "auth_simulator_enabled", True),
    ):
        result = await get_chat_response("Explain tree planting offsets")
        assert result.success is True
        assert "offset" in result.reply.lower() or "tree" in result.reply.lower()


@pytest.mark.asyncio
async def test_chat_simulator_help():
    """Verify simulated response for general/help queries."""
    with (
        patch.object(settings.ai, "gemini_api_key", "YOUR_GEMINI_API_KEY_HERE"),
        patch.object(settings.google, "auth_simulator_enabled", True),
    ):
        result = await get_chat_response("hello chatbot")
        assert result.success is True
        assert (
            "help" in result.reply.lower()
            or "welcome" in result.reply.lower()
            or "carbon" in result.reply.lower()
        )


@pytest.mark.asyncio
async def test_chat_offline_local_knowledge_base():
    """Verify offline local knowledge base when all AI APIs fail."""
    mock_fail = MagicMock()
    mock_fail.status_code = 500
    mock_fail.text = "Service Unavailable"

    # Make API keys valid so it tries them, but mock post to fail
    with (
        patch.object(settings.ai, "gemini_api_key", "valid-key"),
        patch.object(settings.ai, "claude_api_key", "valid-key"),
        patch.object(settings.ai, "chatgpt_api_key", "valid-key"),
        patch.object(settings.ai, "perplexity_api_key", "valid-key"),
        patch.object(settings.ai, "deepseek_api_key", "valid-key"),
        patch.object(settings.google, "auth_simulator_enabled", False),
        patch("httpx.AsyncClient.post", return_value=mock_fail),
    ):
        # 1. Test transport offline match
        result = await get_chat_response("transport car train")
        assert result.provider == "local_knowledge_base"
        assert "offline mode" in result.reply.lower()
        assert "public transit" in result.reply.lower()

        # 2. Test diet offline match
        result = await get_chat_response("meat beef vegan diet")
        assert "meat" in result.reply.lower() or "plant-based" in result.reply.lower()

        # 3. Test energy offline match
        result = await get_chat_response("electricity power solar")
        assert (
            "energy" in result.reply.lower()
            or "solar" in result.reply.lower()
            or "insulation" in result.reply.lower()
        )

        # 4. Test waste offline match
        result = await get_chat_response("waste trash recycling")
        assert "waste" in result.reply.lower() or "recycle" in result.reply.lower()

        # 5. Test offsets offline match
        result = await get_chat_response("offset credit tree")
        assert "offset" in result.reply.lower() or "planting" in result.reply.lower()

        # 6. Test fallback unmatched query
        result = await get_chat_response("completely unrelated query here")
        assert "help with topics" in result.reply


@pytest.mark.asyncio
async def test_call_providers_key_not_configured():
    """Verify that provider calls fail when keys are not configured
    and simulator is disabled.
    """
    from app.services.chat_service import (
        _call_chatgpt,
        _call_claude,
        _call_deepseek,
        _call_gemini,
        _call_perplexity,
    )

    with (
        patch.object(settings.ai, "gemini_api_key", "YOUR_GEMINI_API_KEY_HERE"),
        patch.object(settings.ai, "claude_api_key", "YOUR_CLAUDE_API_KEY_HERE"),
        patch.object(settings.ai, "chatgpt_api_key", "YOUR_CHATGPT_API_KEY_HERE"),
        patch.object(settings.ai, "perplexity_api_key", "YOUR_PERPLEXITY_API_KEY_HERE"),
        patch.object(settings.ai, "deepseek_api_key", "YOUR_DEEPSEEK_API_KEY_HERE"),
        patch.object(settings.google, "auth_simulator_enabled", False),
    ):
        r_gem = await _call_gemini("test")
        assert r_gem.success is False
        assert "key not configured" in r_gem.error

        r_cld = await _call_claude("test")
        assert r_cld.success is False
        assert "key not configured" in r_cld.error

        r_gpt = await _call_chatgpt("test")
        assert r_gpt.success is False
        assert "key not configured" in r_gpt.error

        r_ppx = await _call_perplexity("test")
        assert r_ppx.success is False
        assert "key not configured" in r_ppx.error

        r_dps = await _call_deepseek("test")
        assert r_dps.success is False
        assert "key not configured" in r_dps.error


@pytest.mark.asyncio
async def test_call_providers_timeouts_and_empty_responses():
    """Verify that provider calls handle timeouts, HTTP errors,
    and empty responses correctly.
    """
    import httpx

    from app.services.chat_service import (
        _call_chatgpt,
        _call_claude,
        _call_deepseek,
        _call_gemini,
        _call_perplexity,
    )

    with (
        patch.object(settings.ai, "gemini_api_key", "valid-key"),
        patch.object(settings.ai, "claude_api_key", "valid-key"),
        patch.object(settings.ai, "chatgpt_api_key", "valid-key"),
        patch.object(settings.ai, "perplexity_api_key", "valid-key"),
        patch.object(settings.ai, "deepseek_api_key", "valid-key"),
    ):
        # 1. Timeout handling
        with patch(
            "httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")
        ):
            r_gem = await _call_gemini("test")
            assert r_gem.success is False
            assert "time" in r_gem.error.lower()

            r_cld = await _call_claude("test")
            assert r_cld.success is False
            assert "time" in r_cld.error.lower()

            r_gpt = await _call_chatgpt("test")
            assert r_gpt.success is False
            assert "time" in r_gpt.error.lower()

            r_ppx = await _call_perplexity("test")
            assert r_ppx.success is False
            assert "time" in r_ppx.error.lower()

            r_dps = await _call_deepseek("test")
            assert r_dps.success is False
            assert "time" in r_dps.error.lower()

        # 2. HTTP Error handling
        with patch("httpx.AsyncClient.post", side_effect=httpx.HTTPError("HTTP Error")):
            r_gem = await _call_gemini("test")
            assert r_gem.success is False
            assert "http error" in r_gem.error.lower()

            r_cld = await _call_claude("test")
            assert r_cld.success is False
            assert "http error" in r_cld.error.lower()

            r_gpt = await _call_chatgpt("test")
            assert r_gpt.success is False
            assert "http error" in r_gpt.error.lower()

            r_ppx = await _call_perplexity("test")
            assert r_ppx.success is False
            assert "http error" in r_ppx.error.lower()

            r_dps = await _call_deepseek("test")
            assert r_dps.success is False
            assert "http error" in r_dps.error.lower()

        # 3. Empty/invalid response handling (Status 200 but no choices/parts/content)
        mock_200_empty = MagicMock()
        mock_200_empty.status_code = 200
        mock_200_empty.json.return_value = {}

        with patch("httpx.AsyncClient.post", return_value=mock_200_empty):
            r_gem = await _call_gemini("test")
            assert r_gem.success is False
            assert "empty" in r_gem.error.lower()

            r_cld = await _call_claude("test")
            assert r_cld.success is False
            assert "empty" in r_cld.error.lower()

            r_gpt = await _call_chatgpt("test")
            assert r_gpt.success is False
            assert "empty" in r_gpt.error.lower()

            r_ppx = await _call_perplexity("test")
            assert r_ppx.success is False
            assert "empty" in r_ppx.error.lower()

            r_dps = await _call_deepseek("test")
            assert r_dps.success is False
            assert "empty" in r_dps.error.lower()

        # 4. Bad Status response handling (e.g. 500 API error)
        mock_500 = MagicMock()
        mock_500.status_code = 500
        mock_500.text = "Internal Server Error"

        with patch("httpx.AsyncClient.post", return_value=mock_500):
            r_gem = await _call_gemini("test")
            assert r_gem.success is False
            assert "api error" in r_gem.error.lower() or "500" in r_gem.error

            r_cld = await _call_claude("test")
            assert r_cld.success is False
            assert "api error" in r_cld.error.lower() or "500" in r_cld.error

            r_gpt = await _call_chatgpt("test")
            assert r_gpt.success is False
            assert "api error" in r_gpt.error.lower() or "500" in r_gpt.error

            r_ppx = await _call_perplexity("test")
            assert r_ppx.success is False
            assert "api error" in r_ppx.error.lower() or "500" in r_ppx.error

            r_dps = await _call_deepseek("test")
            assert r_dps.success is False
            assert "api error" in r_dps.error.lower() or "500" in r_dps.error


@pytest.mark.asyncio
async def test_call_claude_chatgpt_simulator():
    """Verify simulated response for Claude and ChatGPT when keys are placeholders."""
    from app.services.chat_service import _call_chatgpt, _call_claude

    with (
        patch.object(settings.ai, "claude_api_key", "YOUR_CLAUDE_API_KEY_HERE"),
        patch.object(settings.ai, "chatgpt_api_key", "YOUR_CHATGPT_API_KEY_HERE"),
        patch.object(settings.google, "auth_simulator_enabled", True),
    ):
        r_cld = await _call_claude("What food should I eat?")
        assert r_cld.success is True
        assert r_cld.provider == "claude"
        assert "diet" in r_cld.reply.lower() or "meat" in r_cld.reply.lower()

        r_gpt = await _call_chatgpt("What food should I eat?")
        assert r_gpt.success is True
        assert r_gpt.provider == "chatgpt"
        assert "diet" in r_gpt.reply.lower() or "meat" in r_gpt.reply.lower()
