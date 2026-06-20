"""Unit and integration tests for carbon calculations."""

import pytest

from app.models import CarbonEntry, EnergyEntry, FoodEntry, TransportEntry, WasteEntry
from app.services.carbon_calculator import calculate_footprint


def test_carbon_calculator_happy_path():
    """Verify correct CO2 calculations under normal scenarios."""
    entry = CarbonEntry(
        transport=[
            TransportEntry(mode="car_petrol", distance_km=100),
            TransportEntry(mode="train", distance_km=50),
        ],
        energy=[
            EnergyEntry(source="electricity", amount_kwh=200),
        ],
        food=[
            FoodEntry(food_type="red_meat", servings=3),
        ],
        waste=[
            WasteEntry(waste_type="landfill", weight_kg=10),
        ],
    )

    # 100 * 0.192 = 19.2
    # 50 * 0.041 = 2.05
    # 200 * 0.233 = 46.6
    # 3 * 6.61 = 19.83
    # 10 * 0.587 = 5.87
    # Total = 19.2 + 2.05 + 46.6 + 19.83 + 5.87 = 93.55
    summary = calculate_footprint(entry)
    assert summary.total_co2_kg == 93.55
    assert len(summary.breakdown) == 4

    # Check breakdown categories
    categories = {item.category: item.co2_kg for item in summary.breakdown}
    assert categories["Transport"] == 21.25
    assert categories["Energy"] == 46.6
    assert categories["Food"] == 19.83
    assert categories["Waste"] == 5.87


def test_carbon_calculator_zero_values():
    """Verify calculator handles zero values properly (should not fail)."""
    entry = CarbonEntry(transport=[], energy=[], food=[], waste=[])
    summary = calculate_footprint(entry)
    assert summary.total_co2_kg == 0.0
    assert summary.rating == "A+"


def test_invalid_values_rejected():
    """Verify input validation rules prevent negative or extremely large values."""
    # Negative distance
    with pytest.raises(ValueError):
        TransportEntry(mode="car_petrol", distance_km=-5)

    # Negative energy
    with pytest.raises(ValueError):
        EnergyEntry(source="electricity", amount_kwh=-10)

    # Too large distance
    with pytest.raises(ValueError):
        TransportEntry(mode="car_petrol", distance_km=1000000)


def test_api_carbon_calculate(client, csrf_tokens):
    """Verify the /api/carbon/calculate endpoint works via API client."""
    headers = {"x-csrf-token": csrf_tokens["token"]}
    cookies = {"csrf_token": csrf_tokens["cookie"]}

    payload = {
        "transport": [{"mode": "car_petrol", "distance_km": 10}],
        "energy": [],
        "food": [],
        "waste": [],
    }

    response = client.post(
        "/api/carbon/calculate", json=payload, headers=headers, cookies=cookies
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_co2_kg"] == 1.92
    assert data["rating"] == "A+"
