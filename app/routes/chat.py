"""AI chatbot route with multi-model fallback.

Delegates to chat_service for the actual AI provider chain.
Input validation handled by Pydantic ChatRequest model.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.models import ChatRequest, ChatResponse
from app.services.analytics import log_analytics_event
from app.services.chat_service import get_chat_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send message to AI chatbot",
    description=(
        "Send a carbon footprint question to the AI chatbot. "
        "Automatically falls back through multiple AI providers: "
        "Gemini -> Claude -> ChatGPT -> Perplexity -> DeepSeek."
    ),
)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process chat request through AI fallback chain.

    Args:
        request: Validated and sanitized ChatRequest.

    Returns:
        ChatResponse with AI-generated reply and provider info.
    """
    try:
        result = await get_chat_response(request.message)

        # Log event to Google Analytics
        session_id = request.session_id or "anonymous_chat_user"
        await log_analytics_event(
            session_id,
            "chat_message_sent",
            {
                "provider": result.provider,
                "fallback_used": str(result.provider != "gemini"),
            },
        )

        return ChatResponse(
            reply=result.reply,
            provider=result.provider,
            fallback_used=(result.provider != "gemini"),
        )

    except Exception as exc:
        logger.error("Chat service error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Chat service temporarily unavailable",
        ) from exc
