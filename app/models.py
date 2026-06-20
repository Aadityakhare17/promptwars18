"""Pydantic models for request/response validation.

Follows YAGNI — only models that are actually used by routes.
All user-facing string fields are sanitized via field validators.
"""

import html
import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# --- Constants ---

_MAX_TEXT_LENGTH = 2000
_DANGEROUS_PATTERN = re.compile(
    r"(<script|javascript:|on\w+=|eval\(|expression\()",
    re.IGNORECASE,
)


# --- Enums ---


class TransportMode(str, Enum):
    """Supported transport modes for carbon calculation."""

    CAR_PETROL = "car_petrol"
    CAR_DIESEL = "car_diesel"
    CAR_ELECTRIC = "car_electric"
    BUS = "bus"
    TRAIN = "train"
    FLIGHT_SHORT = "flight_short"
    FLIGHT_LONG = "flight_long"
    BICYCLE = "bicycle"
    WALKING = "walking"


class EnergySource(str, Enum):
    """Supported energy sources."""

    ELECTRICITY = "electricity"
    NATURAL_GAS = "natural_gas"
    HEATING_OIL = "heating_oil"
    SOLAR = "solar"


class FoodType(str, Enum):
    """Food consumption categories."""

    RED_MEAT = "red_meat"
    POULTRY = "poultry"
    FISH = "fish"
    DAIRY = "dairy"
    VEGETABLES = "vegetables"
    GRAINS = "grains"


class WasteType(str, Enum):
    """Waste disposal categories."""

    LANDFILL = "landfill"
    RECYCLED = "recycled"
    COMPOSTED = "composted"


# --- Sanitization Helpers ---


def _sanitize_text(value: str) -> str:
    """Sanitize user text input against XSS and injection attacks."""
    if len(value) > _MAX_TEXT_LENGTH:
        value = value[:_MAX_TEXT_LENGTH]
    value = html.escape(value, quote=True)
    value = _DANGEROUS_PATTERN.sub("", value)
    return value.strip()


# --- Request Models ---


class TransportEntry(BaseModel):
    """Single transport activity entry."""

    mode: TransportMode
    distance_km: float = Field(
        ..., gt=0, le=50000, description="Distance in kilometers"
    )


class EnergyEntry(BaseModel):
    """Single energy consumption entry."""

    source: EnergySource
    amount_kwh: float = Field(
        ..., gt=0, le=100000, description="Energy in kilowatt-hours"
    )


class FoodEntry(BaseModel):
    """Single food consumption entry."""

    food_type: FoodType
    servings: float = Field(..., gt=0, le=100, description="Number of servings")


class WasteEntry(BaseModel):
    """Single waste disposal entry."""

    waste_type: WasteType
    weight_kg: float = Field(
        ..., gt=0, le=10000, description="Waste weight in kilograms"
    )


class CarbonEntry(BaseModel):
    """Complete carbon footprint entry for calculation."""

    transport: list[TransportEntry] = Field(default_factory=list)
    energy: list[EnergyEntry] = Field(default_factory=list)
    food: list[FoodEntry] = Field(default_factory=list)
    waste: list[WasteEntry] = Field(default_factory=list)

    @field_validator("transport", "energy", "food", "waste")
    @classmethod
    def validate_list_length(cls, value: list) -> list:
        """Prevent oversized lists to avoid DoS via payload inflation."""
        if len(value) > 50:
            raise ValueError("Maximum 50 entries per category")
        return value


class ChatRequest(BaseModel):
    """Chat message from user to AI chatbot."""

    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    session_id: Optional[str] = Field(
        default=None, max_length=64, description="Optional session ID"
    )

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, value: str) -> str:
        """Sanitize chat message against XSS."""
        return _sanitize_text(value)

    @field_validator("session_id")
    @classmethod
    def sanitize_session_id(cls, value: Optional[str]) -> Optional[str]:
        """Validate session ID format."""
        if value is None:
            return value
        if not re.match(r"^[a-zA-Z0-9_-]+$", value):
            raise ValueError("Session ID must be alphanumeric")
        return value


# --- Response Models ---


class CategoryBreakdown(BaseModel):
    """Carbon breakdown for a single category."""

    category: str
    co2_kg: float = Field(..., ge=0, description="CO2 in kilograms")
    percentage: float = Field(..., ge=0, le=100, description="Percentage of total")


class CarbonSummary(BaseModel):
    """Complete carbon footprint calculation result."""

    total_co2_kg: float = Field(..., ge=0)
    breakdown: list[CategoryBreakdown]
    rating: str = Field(..., description="Environmental rating")
    comparison_to_average: str = Field(..., description="Comparison to global average")


class ChatResponse(BaseModel):
    """AI chatbot response."""

    reply: str
    provider: str = Field(..., description="AI provider that generated reply")
    fallback_used: bool = Field(
        default=False, description="Whether a fallback model was used"
    )


class InsightItem(BaseModel):
    """Single actionable insight."""

    title: str
    description: str
    impact: str = Field(..., description="Potential CO2 reduction impact")
    difficulty: str = Field(..., description="Implementation difficulty")


class InsightResponse(BaseModel):
    """Personalized insights response."""

    insights: list[InsightItem]
    highest_impact_category: str
    potential_reduction_kg: float = Field(..., ge=0)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str
