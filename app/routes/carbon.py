"""Carbon footprint tracking and calculation routes.

Provides endpoints for calculating footprint, tracking entries,
and retrieving history. All inputs validated via Pydantic models.
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response

from app.config import settings
from app.models import CarbonEntry, CarbonSummary
from app.services.analytics import log_analytics_event
from app.services.carbon_calculator import calculate_footprint
from app.services.gcs_service import gcs_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/carbon", tags=["carbon"])

# In-memory storage keyed by session — suitable for single-instance
# For production scaling, replace with Redis or database
_session_history: dict[str, list[dict]] = {}


def _get_or_create_session_id(request: Request, response: Response) -> str:
    """Extract or generate and set session ID in cookies.

    Args:
        request: Incoming HTTP request.
        response: Response to set cookie on.

    Returns:
        Session ID string.
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = uuid4().hex[:16]
        is_secure = (request.url.scheme == "https") or (
            request.headers.get("x-forwarded-proto") == "https"
        )
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            samesite="lax",
            secure=is_secure,
            max_age=31536000,  # 1 year
        )
    return session_id


@router.post(
    "/calculate",
    response_model=CarbonSummary,
    summary="Calculate carbon footprint",
    description="Calculate CO2 emissions from transport, energy, food, and waste.",
)
async def calculate_carbon(
    entry: CarbonEntry, request: Request, response: Response
) -> CarbonSummary:
    """Calculate carbon footprint from activity data.

    Args:
        entry: Validated CarbonEntry model.
        request: HTTP request for session.

    Returns:
        CarbonSummary with breakdown and rating.
    """
    try:
        summary = calculate_footprint(entry)
        session_id = _get_or_create_session_id(request, response)
        await log_analytics_event(
            session_id,
            "carbon_calculated",
            {"total_co2": summary.total_co2_kg, "rating": summary.rating},
        )
        return summary
    except Exception as exc:
        logger.error("Calculation error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="An error occurred during calculation",
        ) from exc


@router.post(
    "/track",
    response_model=dict,
    summary="Track carbon entry",
    description="Store a carbon footprint entry in session history.",
)
async def track_entry(entry: CarbonEntry, request: Request, response: Response) -> dict:
    """Store a carbon entry and return its summary.

    Args:
        entry: Validated CarbonEntry model.
        request: HTTP request for session management.
        response: Response to set cookie on.

    Returns:
        Dict with session_id and stored summary.
    """
    session_id = _get_or_create_session_id(request, response)

    # Enforce max history limit
    if session_id in _session_history:
        if len(_session_history[session_id]) >= settings.max_history_entries:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Maximum {settings.max_history_entries} " f"entries per session"
                ),
            )

    summary = calculate_footprint(entry)
    record = {
        "entry": entry.model_dump(),
        "summary": summary.model_dump(),
    }

    _session_history.setdefault(session_id, []).append(record)

    # Upload JSON calculation data to Google Cloud Storage
    blob_name = f"history/{session_id}/{summary.rating}_{uuid4().hex[:8]}.json"
    await gcs_service.upload_json(blob_name, record)

    # Log tracking event to Google Analytics
    await log_analytics_event(
        session_id,
        "carbon_tracked",
        {"total_co2": summary.total_co2_kg, "rating": summary.rating},
    )

    return {"session_id": session_id, "summary": summary.model_dump()}


@router.get(
    "/history",
    response_model=dict,
    summary="Get carbon tracking history",
    description="Retrieve all tracked carbon entries for the current session.",
)
async def get_history(request: Request, response: Response) -> dict:
    """Retrieve tracking history for current session.

    Args:
        request: HTTP request for session identification.
        response: Response to set cookie on.

    Returns:
        Dict with entries list and entry count.
    """
    session_id = _get_or_create_session_id(request, response)
    entries = _session_history.get(session_id, [])

    return {
        "session_id": session_id,
        "entries": entries,
        "count": len(entries),
    }
