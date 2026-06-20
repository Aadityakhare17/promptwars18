"""Multi-model AI chatbot service with automatic fallback chain.

Fallback order: Gemini -> Claude -> ChatGPT -> Perplexity -> DeepSeek.
Fallback triggers: token limit exceeded, rate limit errors, API failures, timeouts.
Each provider is an async function behind a common interface.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import settings
from app.services.http_client import get_http_client

logger = logging.getLogger(__name__)

# System prompt for carbon footprint context
_SYSTEM_PROMPT = (
    "You are a helpful assistant specializing in carbon footprint reduction "
    "and environmental sustainability. Provide accurate, actionable advice "
    "on reducing carbon emissions. Be concise, friendly, and cite specific "
    "numbers when possible. Focus on practical steps individuals can take."
)

# Token/rate limit error indicators per provider
_TOKEN_EXCEEDED_INDICATORS: frozenset[str] = frozenset(
    {
        "token",
        "context_length",
        "max_tokens",
        "rate_limit",
        "quota",
        "exceeded",
        "capacity",
        "overloaded",
    }
)


@dataclass(frozen=True)
class ProviderResult:
    """Result from an AI provider call."""

    reply: str
    provider: str
    success: bool
    error: Optional[str] = None


def _get_simulated_ai_response(message: str, provider_name: str) -> str:
    """Generate a high-quality simulated response from the given AI provider."""
    msg_lower = message.lower()

    # 1. Transportation
    if any(
        k in msg_lower
        for k in [
            "transport",
            "car",
            "drive",
            "flight",
            "fly",
            "vehicle",
            "bus",
            "train",
            "plane",
            "emissions",
        ]
    ):
        return (
            f"Greetings! I am the simulated "
            f"**{provider_name.capitalize()}** assistant. "
            "To reduce your transportation footprint, "
            "here are actionable recommendations:\n\n"
            "1. **Switch to Public Transit or Active Travel**: "
            "Opting for trains, buses, biking, or walking "
            "can reduce your commute emissions by up to 70% "
            "compared to driving alone.\n"
            "2. **Transition to Electric Vehicles (EVs)**: "
            "Electric cars emit zero direct tailpipe emissions. "
            "Even when accounting for electricity grids, they "
            "reduce lifetime CO₂ by over 50% in most regions.\n"
            "3. **Minimize Air Travel**: Flying is highly carbon-intensive. "
            "One round-trip trans-atlantic flight "
            "can emit more CO₂ than an average person's home heating "
            "for an entire year. Consider virtual meetings "
            "or trains for regional travel.\n"
            "4. **Eco-Driving Techniques**: Keep tires properly inflated "
            "(improves mileage by 3%), avoid sudden "
            "acceleration, and remove excess weight to optimize "
            "fuel efficiency."
        )

    # 2. Diet / Food
    if any(
        k in msg_lower
        for k in [
            "diet",
            "food",
            "meat",
            "beef",
            "eat",
            "vegan",
            "vegetarian",
            "dairy",
            "meal",
        ]
    ):
        return (
            f"Hello! I am the simulated "
            f"**{provider_name.capitalize()}** assistant. "
            "Adjusting your diet is one of the most effective ways "
            "to lower your personal carbon footprint:\n\n"
            "1. **Reduce Animal Products**: Red meats like beef and lamb "
            "generate up to 10-30 times more greenhouse "
            "gases than plant-based proteins due to methane emissions "
            "from enteric fermentation and land use.\n"
            "2. **Adopt a Plant-Forward Diet**: Incorporating more grains, "
            "beans, lentils, and fresh vegetables "
            "can reduce your dietary carbon emissions by up to 50%.\n"
            "3. **Zero Waste Cooking**: About one-third of all food "
            "produced globally is wasted. Food waste decomposing "
            "in landfills produces methane. Plan meals, freeze leftovers, "
            "and compost scraps.\n"
            "4. **Source Locally and Seasonally**: Reduce food miles and "
            "energy-intensive greenhouse growing by buying "
            "locally grown, seasonal produce."
        )

    # 3. Energy
    if any(
        k in msg_lower
        for k in [
            "energy",
            "electricity",
            "power",
            "solar",
            "heat",
            "ac",
            "light",
            "coal",
            "gas",
        ]
    ):
        return (
            f"Hello! I am the simulated "
            f"**{provider_name.capitalize()}** assistant. "
            "Your home's energy consumption is a major footprint "
            "category. Here is how to optimize it:\n\n"
            "1. **Upgrade to Smart Thermostats**: Optimizing heating and "
            "cooling schedules can save up to 10-15% "
            "on utility bills and prevent unnecessary heating/cooling "
            "emissions.\n"
            "2. **Switch to Renewable Power**: Transition your home "
            "electricity tariff to a green/renewable tariff, "
            "or install rooftop solar panels to generate clean "
            "energy directly.\n"
            "3. **Energy Efficiency Upgrades**: Switch to LED bulbs "
            "(uses 75% less energy than incandescent bulbs), "
            "insulate walls and roofs, and choose ENERGY STAR "
            "certified appliances.\n"
            "4. **Unplug Phantom Loads**: Electronics draw power even "
            "when turned off. Use smart power strips to shut off "
            "power to devices when they are not active."
        )

    # 4. Waste / Recycling
    if any(
        k in msg_lower
        for k in [
            "waste",
            "trash",
            "recycle",
            "garbage",
            "compost",
            "plastic",
            "landfill",
        ]
    ):
        return (
            f"Hello! I am the simulated "
            f"**{provider_name.capitalize()}** assistant. "
            "Reducing and managing household waste keeps carbon and "
            "methane emissions down:\n\n"
            "1. **Compost Organics**: Organic waste in landfill decomposes "
            "anaerobically to produce methane. Composting "
            "returns nutrients to the soil and keeps organic matter "
            "out of landfills.\n"
            "2. **Minimize Single-Use Plastics**: Production of plastics is "
            "extremely carbon-intensive. Choose reusable "
            "water bottles, bags, and containers to reduce demand "
            "for new plastic production.\n"
            "3. **Recycle Correctly**: Clean and sort paper, cardboard, "
            "glass, and aluminum. Recycling aluminum saves "
            "95% of the energy required to make it from raw materials.\n"
            "4. **Refuse and Reduce**: The most effective step is "
            "refusing unnecessary packaging and reducing purchases."
        )

    # 5. Offsets
    if any(
        k in msg_lower for k in ["offset", "compensate", "neutral", "credit", "tree"]
    ):
        return (
            f"Hello! I am the simulated "
            f"**{provider_name.capitalize()}** assistant. "
            "Carbon offsetting should be your final step after "
            "reducing emissions as much as possible:\n\n"
            "1. **Carbon Mitigation Hierarchy**: Avoid emissions first, "
            "reduce second, and offset only the remaining "
            "unavoidable emissions.\n"
            "2. **Verify Offset Quality**: Look for projects certified by "
            "robust, third-party standards such as the Gold "
            "Standard, Verified Carbon Standard (VCS), or Climate "
            "Action Reserve.\n"
            "3. **Types of Projects**: Support projects that offer "
            "long-term carbon removal (like reforestation and biochar) "
            "or verified avoidance (like landfill gas capture and clean "
            "cookstove distribution)."
        )

    # 6. General / Introduction
    return (
        f"Hi there! I am your **{provider_name.capitalize()}** "
        f"sustainability assistant (running in simulated mode). "
        "I can answer questions and provide detailed recommendations "
        "on how to reduce your carbon footprint "
        "across key lifestyle areas:\n\n"
        "- 🚗 **Transportation**: Commuting, vehicles, electric cars, "
        "and flights.\n"
        "- 🍽️ **Diet & Food**: Plant-based meals, animal products, "
        "and reducing food waste.\n"
        "- ⚡ **Home Energy**: Renewable electricity, energy efficiency, "
        "smart heating/cooling.\n"
        "- 🗑️ **Waste & Recycling**: Composting, recycling, "
        "single-use plastics, and circular economy.\n"
        "- 🌳 **Carbon Offsetting**: High-quality offset credits, "
        "reforestation, and neutral projects.\n\n"
        "How can I help you take green action today?"
    )


async def _call_gemini(message: str) -> ProviderResult:
    """Call Google Gemini API.

    Args:
        message: User message string.

    Returns:
        ProviderResult with reply or error.
    """
    api_key = settings.ai.gemini_api_key
    if api_key == "YOUR_GEMINI_API_KEY_HERE":
        if settings.google.auth_simulator_enabled:
            return ProviderResult(
                reply=_get_simulated_ai_response(message, "gemini"),
                provider="gemini",
                success=True,
            )
        return ProviderResult(
            reply="",
            provider="gemini",
            success=False,
            error="Gemini API key not configured",
        )

    url = (
        f"{settings.ai.gemini_api_url}/"
        f"{settings.ai.gemini_model}:generateContent"
        f"?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": f"{_SYSTEM_PROMPT}\n\nUser: {message}"}]}],
        "generationConfig": {
            "maxOutputTokens": 1024,
            "temperature": 0.7,
        },
    }

    try:
        client = get_http_client()
        response = await client.post(url, json=payload)

        if response.status_code == 200:
            data = response.json()
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            if text:
                return ProviderResult(reply=text, provider="gemini", success=True)
            return ProviderResult(
                reply="",
                provider="gemini",
                success=False,
                error="Empty response from Gemini",
            )

        return ProviderResult(
            reply="",
            provider="gemini",
            success=False,
            error=f"Gemini API error {response.status_code}: {response.text[:200]}",
        )

    except httpx.TimeoutException:
        return ProviderResult(
            reply="",
            provider="gemini",
            success=False,
            error="Gemini request timed out",
        )
    except httpx.HTTPError as exc:
        return ProviderResult(
            reply="",
            provider="gemini",
            success=False,
            error=f"Gemini HTTP error: {str(exc)[:200]}",
        )


async def _call_claude(message: str) -> ProviderResult:
    """Call Anthropic Claude API.

    Args:
        message: User message string.

    Returns:
        ProviderResult with reply or error.
    """
    api_key = settings.ai.claude_api_key
    if api_key == "YOUR_CLAUDE_API_KEY_HERE":
        if settings.google.auth_simulator_enabled:
            return ProviderResult(
                reply=_get_simulated_ai_response(message, "claude"),
                provider="claude",
                success=True,
            )
        return ProviderResult(
            reply="",
            provider="claude",
            success=False,
            error="Claude API key not configured",
        )

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": settings.ai.claude_model,
        "max_tokens": 1024,
        "system": _SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": message}],
    }

    try:
        client = get_http_client()
        response = await client.post(
            settings.ai.claude_api_url,
            headers=headers,
            json=payload,
        )

        if response.status_code == 200:
            data = response.json()
            content_blocks = data.get("content", [])
            text = "".join(
                block.get("text", "")
                for block in content_blocks
                if block.get("type") == "text"
            )
            if text:
                return ProviderResult(reply=text, provider="claude", success=True)
            return ProviderResult(
                reply="",
                provider="claude",
                success=False,
                error="Empty response from Claude",
            )

        return ProviderResult(
            reply="",
            provider="claude",
            success=False,
            error=f"Claude API error {response.status_code}: {response.text[:200]}",
        )

    except httpx.TimeoutException:
        return ProviderResult(
            reply="",
            provider="claude",
            success=False,
            error="Claude request timed out",
        )
    except httpx.HTTPError as exc:
        return ProviderResult(
            reply="",
            provider="claude",
            success=False,
            error=f"Claude HTTP error: {str(exc)[:200]}",
        )


async def _call_openai_compatible(
    message: str,
    api_key: str,
    placeholder: str,
    model: str,
    api_url: str,
    provider_name: str,
) -> ProviderResult:
    """Call an OpenAI-compatible API (ChatGPT, Perplexity, DeepSeek).

    Args:
        message: User message string.
        api_key: API key for the provider.
        placeholder: Placeholder string to check if key is configured.
        model: Model identifier string.
        api_url: API endpoint URL.
        provider_name: Human-readable provider name.

    Returns:
        ProviderResult with reply or error.
    """
    if api_key == placeholder:
        if settings.google.auth_simulator_enabled:
            return ProviderResult(
                reply=_get_simulated_ai_response(message, provider_name),
                provider=provider_name,
                success=True,
            )
        return ProviderResult(
            reply="",
            provider=provider_name,
            success=False,
            error=f"{provider_name} API key not configured",
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        "max_tokens": 1024,
        "temperature": 0.7,
    }

    try:
        client = get_http_client()
        response = await client.post(api_url, headers=headers, json=payload)

        if response.status_code == 200:
            data = response.json()
            choices = data.get("choices", [])
            if choices:
                text = choices[0].get("message", {}).get("content", "")
                if text:
                    return ProviderResult(
                        reply=text,
                        provider=provider_name,
                        success=True,
                    )
            return ProviderResult(
                reply="",
                provider=provider_name,
                success=False,
                error=f"Empty response from {provider_name}",
            )

        return ProviderResult(
            reply="",
            provider=provider_name,
            success=False,
            error=(
                f"{provider_name} API error {response.status_code}: "
                f"{response.text[:200]}"
            ),
        )

    except httpx.TimeoutException:
        return ProviderResult(
            reply="",
            provider=provider_name,
            success=False,
            error=f"{provider_name} request timed out",
        )
    except httpx.HTTPError as exc:
        return ProviderResult(
            reply="",
            provider=provider_name,
            success=False,
            error=f"{provider_name} HTTP error: {str(exc)[:200]}",
        )


async def _call_chatgpt(message: str) -> ProviderResult:
    """Call OpenAI ChatGPT API."""
    return await _call_openai_compatible(
        message=message,
        api_key=settings.ai.chatgpt_api_key,
        placeholder="YOUR_CHATGPT_API_KEY_HERE",
        model=settings.ai.chatgpt_model,
        api_url=settings.ai.chatgpt_api_url,
        provider_name="chatgpt",
    )


async def _call_perplexity(message: str) -> ProviderResult:
    """Call Perplexity API."""
    return await _call_openai_compatible(
        message=message,
        api_key=settings.ai.perplexity_api_key,
        placeholder="YOUR_PERPLEXITY_API_KEY_HERE",
        model=settings.ai.perplexity_model,
        api_url=settings.ai.perplexity_api_url,
        provider_name="perplexity",
    )


async def _call_deepseek(message: str) -> ProviderResult:
    """Call DeepSeek API."""
    return await _call_openai_compatible(
        message=message,
        api_key=settings.ai.deepseek_api_key,
        placeholder="YOUR_DEEPSEEK_API_KEY_HERE",
        model=settings.ai.deepseek_model,
        api_url=settings.ai.deepseek_api_url,
        provider_name="deepseek",
    )


# Ordered fallback chain — Gemini first, then alternatives
_PROVIDER_CHAIN = [
    _call_gemini,
    _call_claude,
    _call_chatgpt,
    _call_perplexity,
    _call_deepseek,
]

_LOCAL_KNOWLEDGE_BASE = {
    "transport": (
        "Transportation is a major contributor to carbon footprints. To reduce it:\n"
        "1. Avoid driving alone; carpool, bike, or walk where possible.\n"
        "2. Switch to public transit or an electric/hybrid vehicle.\n"
        "3. Limit flights: air travel emits high amounts of CO2 per passenger mile.\n"
        "4. Keep your car well-maintained (inflated tires improve fuel economy)."
    ),
    "diet": (
        "Food accounts for a significant portion of household emissions. "
        "To lower your food footprint:\n"
        "1. Reduce red meat (beef, lamb) and dairy consumption - they have "
        "the highest carbon intensity.\n"
        "2. Eat more plant-based meals (beans, lentils, grains).\n"
        "3. Minimize food waste: plan meals, store food properly, "
        "and compost scraps.\n"
        "4. Buy local and seasonal produce to reduce transportation emissions."
    ),
    "energy": (
        "Home energy use is another primary driver of personal carbon footprints. "
        "To optimize:\n"
        "1. Switch to LED lighting and turn off lights/appliances when "
        "not in use.\n"
        "2. Install a programmable thermostat to optimize heating/cooling.\n"
        "3. Insulate walls, windows, and doors to improve thermal efficiency.\n"
        "4. Transition to renewable energy sources, such as home solar panels "
        "or green tariffs."
    ),
    "waste": (
        "Waste management plays a crucial role in carbon emissions. To help:\n"
        "1. Practice the 3 Rs: Reduce, Reuse, and Recycle correctly.\n"
        "2. Compost organic waste instead of throwing it in the trash.\n"
        "3. Avoid single-use plastics by carrying reusable bottles and bags.\n"
        "4. Support circular economy brands and buy durable products."
    ),
    "offset": (
        "Carbon offsetting helps neutralize emissions you cannot avoid. "
        "Best practices:\n"
        "1. Reduce your emissions as much as possible *before* buying offsets.\n"
        "2. Look for certified offset projects (Gold Standard, VCS, "
        "Climate Action Reserve).\n"
        "3. Focus on high-quality projects like reforestation, methane capture, "
        "or renewable energy."
    ),
}


def _get_local_response(message: str) -> str:
    """Scan query for keywords and return matched local carbon advice."""
    msg_lower = message.lower()
    matches = []

    if any(
        k in msg_lower
        for k in [
            "transport",
            "car",
            "drive",
            "flight",
            "fly",
            "vehicle",
            "bus",
            "train",
            "plane",
        ]
    ):
        matches.append(_LOCAL_KNOWLEDGE_BASE["transport"])
    if any(
        k in msg_lower
        for k in [
            "diet",
            "food",
            "meat",
            "beef",
            "eat",
            "vegan",
            "vegetarian",
            "dairy",
            "meal",
        ]
    ):
        matches.append(_LOCAL_KNOWLEDGE_BASE["diet"])
    if any(
        k in msg_lower
        for k in [
            "energy",
            "electricity",
            "power",
            "solar",
            "heat",
            "ac",
            "light",
            "coal",
            "gas",
        ]
    ):
        matches.append(_LOCAL_KNOWLEDGE_BASE["energy"])
    if any(
        k in msg_lower
        for k in [
            "waste",
            "trash",
            "recycle",
            "garbage",
            "compost",
            "plastic",
            "landfill",
        ]
    ):
        matches.append(_LOCAL_KNOWLEDGE_BASE["waste"])
    if any(
        k in msg_lower for k in ["offset", "compensate", "neutral", "credit", "tree"]
    ):
        matches.append(_LOCAL_KNOWLEDGE_BASE["offset"])

    if matches:
        return "\n\n---\n\n".join(matches)

    return (
        "I can help with topics like "
        "Transportation, Diet/Food, Home Energy, Waste/Recycling, and Carbon Offsets. "
        "Please ask a question related to one of these areas!"
    )


async def get_chat_response(message: str) -> ProviderResult:
    """Get AI response using fallback chain.

    Tries each provider in order. Falls back on:
    - Token/rate limit exceeded
    - API errors
    - Timeouts
    - Empty responses
    - Offline local database if all providers fail
    """
    errors: list[str] = []

    for provider_fn in _PROVIDER_CHAIN:
        result = await provider_fn(message)

        if result.success:
            return ProviderResult(
                reply=result.reply,
                provider=result.provider,
                success=True,
                error=None,
            )

        error_msg = result.error or "Unknown error"
        errors.append(f"{result.provider}: {error_msg}")
        logger.warning(
            "Provider %s failed: %s — trying next",
            result.provider,
            error_msg,
        )

    # All providers failed
    combined_errors = "; ".join(errors)
    logger.error("All AI providers failed: %s", combined_errors)

    local_reply = _get_local_response(message)
    return ProviderResult(
        reply=(
            "I am currently operating in offline mode as connection to AI services "
            "is unavailable, but here is some helpful information on your topic:\n\n"
            f"{local_reply}"
        ),
        provider="local_knowledge_base",
        success=True,
        error=combined_errors,
    )
