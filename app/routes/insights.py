"""Personalized insights route.

Accepts a CarbonEntry, computes the footprint, then generates
targeted recommendations based on the highest-impact category.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.models import CarbonEntry, InsightResponse
from app.services.analytics import log_analytics_event
from app.services.carbon_calculator import calculate_footprint
from app.services.insights_engine import generate_insights

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["insights"])


def _get_session_id(request: Request) -> str:
    """Extract or fallback session ID from request."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = "anonymous_insights_user"
    return session_id


@router.post(
    "/insights",
    response_model=InsightResponse,
    summary="Get personalized insights",
    description=(
        "Analyze your carbon footprint and receive personalized, "
        "actionable recommendations to reduce emissions."
    ),
)
async def get_insights(entry: CarbonEntry, request: Request) -> InsightResponse:
    """Generate personalized insights from carbon data.

    Args:
        entry: Validated CarbonEntry with activity data.
        request: HTTP request for session.

    Returns:
        InsightResponse with tips and reduction estimates.
    """
    try:
        summary = calculate_footprint(entry)
        response = generate_insights(summary)

        # Log event to Google Analytics
        session_id = _get_session_id(request)
        await log_analytics_event(
            session_id,
            "insights_viewed",
            {"highest_impact": response.highest_impact_category},
        )

        return response
    except Exception as exc:
        logger.error("Insights generation error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="An error occurred generating insights",
        ) from exc
