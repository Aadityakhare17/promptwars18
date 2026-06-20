"""Carbon footprint calculator service.

Uses EPA and DEFRA emission factors for accurate CO2 calculations.
All lookups are O(1) via dictionaries. Single-pass computation over entries.
"""

from app.models import (
    CarbonEntry,
    CarbonSummary,
    CategoryBreakdown,
    EnergySource,
    FoodType,
    TransportMode,
    WasteType,
)

# Emission factors in kg CO2 per unit
# Transport: kg CO2 per kilometer
TRANSPORT_FACTORS: dict[TransportMode, float] = {
    TransportMode.CAR_PETROL: 0.192,
    TransportMode.CAR_DIESEL: 0.171,
    TransportMode.CAR_ELECTRIC: 0.053,
    TransportMode.BUS: 0.089,
    TransportMode.TRAIN: 0.041,
    TransportMode.FLIGHT_SHORT: 0.255,
    TransportMode.FLIGHT_LONG: 0.195,
    TransportMode.BICYCLE: 0.0,
    TransportMode.WALKING: 0.0,
}

# Energy: kg CO2 per kWh
ENERGY_FACTORS: dict[EnergySource, float] = {
    EnergySource.ELECTRICITY: 0.233,
    EnergySource.NATURAL_GAS: 0.184,
    EnergySource.HEATING_OIL: 0.266,
    EnergySource.SOLAR: 0.020,
}

# Food: kg CO2 per serving
FOOD_FACTORS: dict[FoodType, float] = {
    FoodType.RED_MEAT: 6.61,
    FoodType.POULTRY: 1.82,
    FoodType.FISH: 1.34,
    FoodType.DAIRY: 1.39,
    FoodType.VEGETABLES: 0.37,
    FoodType.GRAINS: 0.51,
}

# Waste: kg CO2 per kg of waste
WASTE_FACTORS: dict[WasteType, float] = {
    WasteType.LANDFILL: 0.587,
    WasteType.RECYCLED: 0.021,
    WasteType.COMPOSTED: 0.010,
}

# Global average annual CO2 per capita (tonnes)
_GLOBAL_AVERAGE_ANNUAL_CO2_TONNES = 4.7


def _compute_category_total(entries: list, factor_map: dict, value_attr: str) -> float:
    """Compute total CO2 for a category in a single pass.

    Args:
        entries: List of Pydantic entry models.
        factor_map: Dict mapping entry type to emission factor.
        value_attr: Attribute name holding the quantity value.

    Returns:
        Total CO2 in kilograms.
    """
    return sum(
        factor_map[getattr(entry, _get_type_attr(entry))] * getattr(entry, value_attr)
        for entry in entries
    )


def _get_type_attr(entry: object) -> str:
    """Determine the type attribute name for an entry model.

    Args:
        entry: Pydantic entry model instance.

    Returns:
        Attribute name string.
    """
    # Map entry class to its type field name
    type_attrs = {
        "TransportEntry": "mode",
        "EnergyEntry": "source",
        "FoodEntry": "food_type",
        "WasteEntry": "waste_type",
    }
    return type_attrs[entry.__class__.__name__]


def _get_rating(total_kg: float) -> str:
    """Assign an environmental rating based on total CO2.

    Uses a tiered system aligned with climate science targets.

    Args:
        total_kg: Total CO2 in kilograms.

    Returns:
        Rating string from A+ (excellent) to F (critical).
    """
    if total_kg <= 5:
        return "A+"
    if total_kg <= 20:
        return "A"
    if total_kg <= 50:
        return "B"
    if total_kg <= 100:
        return "C"
    if total_kg <= 200:
        return "D"
    return "F"


def _get_comparison(total_kg: float) -> str:
    """Compare footprint to global average.

    Args:
        total_kg: Total CO2 in kilograms.

    Returns:
        Human-readable comparison string.
    """
    daily_average_kg = (_GLOBAL_AVERAGE_ANNUAL_CO2_TONNES * 1000) / 365
    ratio = total_kg / daily_average_kg if daily_average_kg > 0 else 0

    if ratio < 0.5:
        return "Well below global daily average — excellent!"
    if ratio < 1.0:
        return "Below global daily average — good progress!"
    if ratio < 1.5:
        return "Near the global daily average."
    if ratio < 2.0:
        return "Above global daily average — room for improvement."
    return "Significantly above global daily average — action needed."


def calculate_footprint(entry: CarbonEntry) -> CarbonSummary:
    """Calculate total carbon footprint from all categories.

    Single-pass computation per category with O(1) factor lookups.

    Args:
        entry: Validated CarbonEntry with all activity data.

    Returns:
        CarbonSummary with breakdown, rating, and comparison.
    """
    # Compute each category total in a single pass
    category_totals: dict[str, float] = {
        "Transport": _compute_category_total(
            entry.transport, TRANSPORT_FACTORS, "distance_km"
        ),
        "Energy": _compute_category_total(entry.energy, ENERGY_FACTORS, "amount_kwh"),
        "Food": _compute_category_total(entry.food, FOOD_FACTORS, "servings"),
        "Waste": _compute_category_total(entry.waste, WASTE_FACTORS, "weight_kg"),
    }

    total = sum(category_totals.values())

    # Build breakdown with percentages — single pass
    breakdown = [
        CategoryBreakdown(
            category=category,
            co2_kg=round(co2, 3),
            percentage=round((co2 / total * 100) if total > 0 else 0, 1),
        )
        for category, co2 in category_totals.items()
    ]

    return CarbonSummary(
        total_co2_kg=round(total, 3),
        breakdown=breakdown,
        rating=_get_rating(total),
        comparison_to_average=_get_comparison(total),
    )
