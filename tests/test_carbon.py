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


def test_api_carbon_track_and_history(client, csrf_tokens):
    """Verify tracking and history retrieval endpoints."""
    headers = {"x-csrf-token": csrf_tokens["token"]}
    cookies = {"csrf_token": csrf_tokens["cookie"]}

    payload = {
        "transport": [{"mode": "car_petrol", "distance_km": 50}],
        "energy": [],
        "food": [],
        "waste": [],
    }

    # 1. Track entry
    track_resp = client.post(
        "/api/carbon/track", json=payload, headers=headers, cookies=cookies
    )
    assert track_resp.status_code == 200
    track_data = track_resp.json()
    assert "session_id" in track_data
    assert track_data["summary"]["total_co2_kg"] == 9.6

    # 2. Get history (should have 1 entry)
    cookies["session_id"] = track_resp.cookies.get("session_id")
    history_resp = client.get("/api/carbon/history", cookies=cookies)
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert history_data["count"] == 1
    assert len(history_data["entries"]) == 1
    assert history_data["entries"][0]["summary"]["total_co2_kg"] == 9.6


def test_api_carbon_track_limit(client, csrf_tokens):
    """Verify that tracking limit is enforced."""
    from unittest.mock import patch

    from app.config import settings

    headers = {"x-csrf-token": csrf_tokens["token"]}
    cookies = {"csrf_token": csrf_tokens["cookie"]}

    payload = {
        "transport": [],
        "energy": [],
        "food": [],
        "waste": [],
    }

    with patch.object(settings, "max_history_entries", 1):
        # First track should succeed
        resp1 = client.post(
            "/api/carbon/track", json=payload, headers=headers, cookies=cookies
        )
        assert resp1.status_code == 200

        # Second track should exceed limit and fail with 400
        resp2 = client.post(
            "/api/carbon/track", json=payload, headers=headers, cookies=cookies
        )
        assert resp2.status_code == 400
        assert "Maximum 1 entries per session" in resp2.json()["detail"]


def test_api_carbon_calculate_error(client, csrf_tokens):
    """Verify calculation endpoint returns 500 when calculator raises exception."""
    from unittest.mock import patch

    headers = {"x-csrf-token": csrf_tokens["token"]}
    cookies = {"csrf_token": csrf_tokens["cookie"]}

    payload = {
        "transport": [],
        "energy": [],
        "food": [],
        "waste": [],
    }

    with patch(
        "app.routes.carbon.calculate_footprint", side_effect=Exception("Calc failure")
    ):
        resp = client.post(
            "/api/carbon/calculate", json=payload, headers=headers, cookies=cookies
        )
        assert resp.status_code == 500
        assert "An error occurred during calculation" in resp.json()["detail"]


def test_carbon_calculator_rating_b_and_above_average():
    """Verify B rating and above-average daily comparison threshold."""
    entry = CarbonEntry(
        transport=[
            TransportEntry(mode="car_petrol", distance_km=114.5833)
        ],  # 22 kg CO2
        energy=[],
        food=[],
        waste=[],
    )
    summary = calculate_footprint(entry)
    assert summary.rating == "B"
    assert "Above global daily average" in summary.comparison_to_average


def test_carbon_calculator_rating_d_and_significantly_above():
    """Verify D rating and significantly above-average daily comparison threshold."""
    entry = CarbonEntry(
        transport=[TransportEntry(mode="car_petrol", distance_km=781.25)],  # 150 kg CO2
        energy=[],
        food=[],
        waste=[],
    )
    summary = calculate_footprint(entry)
    assert summary.rating == "D"
    assert "Significantly above global daily average" in summary.comparison_to_average
