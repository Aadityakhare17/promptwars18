"""Unit and integration tests for personalized insights."""

from app.models import CarbonEntry, EnergyEntry, TransportEntry
from app.services.carbon_calculator import calculate_footprint
from app.services.insights_engine import generate_insights


def test_insights_transport_heavy():
    """Verify transport-heavy profiles yield transport insights."""
    entry = CarbonEntry(
        transport=[TransportEntry(mode="car_petrol", distance_km=500)],
        energy=[],
        food=[],
        waste=[],
    )
    summary = calculate_footprint(entry)
    response = generate_insights(summary)

    assert response.highest_impact_category == "Transport"
    assert len(response.insights) == 3
    # Check that at least the top recommendation is transport-related
    assert (
        "transit" in response.insights[0].title.lower()
        or "vehicle" in response.insights[0].title.lower()
        or "carpool" in response.insights[0].title.lower()
    )


def test_insights_energy_heavy():
    """Verify energy-heavy profiles yield energy insights."""
    entry = CarbonEntry(
        transport=[],
        energy=[EnergyEntry(source="electricity", amount_kwh=1000)],
        food=[],
        waste=[],
    )
    summary = calculate_footprint(entry)
    response = generate_insights(summary)

    assert response.highest_impact_category == "Energy"
    assert len(response.insights) == 3
    assert (
        "renewable" in response.insights[0].title.lower()
        or "insulation" in response.insights[0].title.lower()
    )


def test_insights_api(client, csrf_tokens):
    """Verify the /api/insights endpoint works and responds correctly."""
    headers = {"x-csrf-token": csrf_tokens["token"]}
    cookies = {"csrf_token": csrf_tokens["cookie"]}

    payload = {
        "transport": [{"mode": "car_petrol", "distance_km": 100}],
        "energy": [],
        "food": [],
        "waste": [],
    }

    response = client.post(
        "/api/insights", json=payload, headers=headers, cookies=cookies
    )
    assert response.status_code == 200
    data = response.json()
    assert "insights" in data
    assert data["highest_impact_category"] == "Transport"
    assert len(data["insights"]) == 3


def test_insights_api_error(client, csrf_tokens):
    """Verify insights endpoint returns 500 when insights engine raises exception."""
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
        "app.routes.insights.generate_insights",
        side_effect=Exception("Insights engine error"),
    ):
        response = client.post(
            "/api/insights", json=payload, headers=headers, cookies=cookies
        )
        assert response.status_code == 500
        assert "An error occurred generating insights" in response.json()["detail"]


def test_insights_fallback_padding():
    """Verify that insights generator pads tips when category has no preset tips."""
    from app.models import CarbonSummary, CategoryBreakdown
    from app.services.insights_engine import generate_insights

    summary = CarbonSummary(
        total_co2_kg=100.0,
        breakdown=[
            CategoryBreakdown(category="Unknown", co2_kg=100.0, percentage=100.0)
        ],
        rating="D",
        comparison_to_average="above",
    )

    response = generate_insights(summary)
    assert response.highest_impact_category == "Unknown"
    assert len(response.insights) == 3
    assert response.potential_reduction_kg == 30.0
