"""Personalized insights engine.

Rule-based recommendation system that identifies the highest-impact
category and returns actionable tips. No unnecessary AI calls (YAGNI).
Tips database is pre-sorted by impact — no runtime sorting needed.
"""

from app.models import (
    CarbonSummary,
    InsightItem,
    InsightResponse,
)

# Pre-sorted tips database — highest impact first per category
_TIPS_DATABASE: dict[str, list[InsightItem]] = {
    "Transport": [
        InsightItem(
            title="Switch to public transit",
            description=(
                "Replace car commutes with bus or train. "
                "A 20km daily commute by train instead of car "
                "saves ~1,100 kg CO2 per year."
            ),
            impact="Up to 1,100 kg CO2/year",
            difficulty="Medium",
        ),
        InsightItem(
            title="Consider an electric vehicle",
            description=(
                "EVs produce 50-70% less emissions than petrol cars "
                "over their lifetime, even accounting for manufacturing."
            ),
            impact="Up to 2,000 kg CO2/year",
            difficulty="High",
        ),
        InsightItem(
            title="Carpool or ride-share",
            description=(
                "Sharing rides with 2-3 people cuts per-person "
                "transport emissions by 50-66%."
            ),
            impact="Up to 800 kg CO2/year",
            difficulty="Low",
        ),
        InsightItem(
            title="Reduce short flights",
            description=(
                "Replace flights under 500km with train travel. "
                "A single short flight emits ~255g CO2 per km vs "
                "~41g for trains."
            ),
            impact="Up to 500 kg CO2/trip",
            difficulty="Medium",
        ),
    ],
    "Energy": [
        InsightItem(
            title="Switch to renewable energy",
            description=(
                "Choose a green energy provider or install solar panels. "
                "Solar reduces household emissions by up to 80%."
            ),
            impact="Up to 1,500 kg CO2/year",
            difficulty="Medium",
        ),
        InsightItem(
            title="Improve home insulation",
            description=(
                "Proper insulation reduces heating energy by 25-40%. "
                "Start with loft and cavity wall insulation."
            ),
            impact="Up to 600 kg CO2/year",
            difficulty="High",
        ),
        InsightItem(
            title="Use LED lighting",
            description=(
                "Replace all bulbs with LEDs. They use 75% less energy "
                "and last 25x longer than incandescent bulbs."
            ),
            impact="Up to 100 kg CO2/year",
            difficulty="Low",
        ),
    ],
    "Food": [
        InsightItem(
            title="Reduce red meat consumption",
            description=(
                "Replacing beef with plant-based meals 3 days a week "
                "can save over 500 kg CO2 per year. "
                "Beef produces 6.6 kg CO2 per serving."
            ),
            impact="Up to 600 kg CO2/year",
            difficulty="Medium",
        ),
        InsightItem(
            title="Buy local and seasonal produce",
            description=(
                "Local food reduces transport emissions by up to 50%. "
                "Seasonal produce avoids energy-intensive greenhouse farming."
            ),
            impact="Up to 300 kg CO2/year",
            difficulty="Low",
        ),
        InsightItem(
            title="Reduce food waste",
            description=(
                "The average household wastes 30% of purchased food. "
                "Plan meals and use leftovers to cut waste emissions."
            ),
            impact="Up to 200 kg CO2/year",
            difficulty="Low",
        ),
    ],
    "Waste": [
        InsightItem(
            title="Maximize recycling",
            description=(
                "Recycling reduces waste emissions by 96% compared to "
                "landfill. Separate paper, plastic, glass, and metal."
            ),
            impact="Up to 300 kg CO2/year",
            difficulty="Low",
        ),
        InsightItem(
            title="Start composting",
            description=(
                "Composting organic waste prevents methane emissions "
                "from landfills. Home composting is simple and effective."
            ),
            impact="Up to 200 kg CO2/year",
            difficulty="Low",
        ),
        InsightItem(
            title="Reduce single-use plastics",
            description=(
                "Use reusable bags, bottles, and containers. "
                "Plastic production is energy-intensive and creates "
                "long-lived pollution."
            ),
            impact="Up to 100 kg CO2/year",
            difficulty="Low",
        ),
    ],
}


def generate_insights(summary: CarbonSummary) -> InsightResponse:
    """Generate personalized insights based on carbon footprint summary.

    Identifies the highest-impact category and returns top 3 tips.
    Tips are pre-sorted — no runtime sorting needed.

    Args:
        summary: Calculated CarbonSummary with category breakdowns.

    Returns:
        InsightResponse with actionable recommendations.
    """
    # Find highest-impact category — single pass O(n) where n=4
    highest_category = "Transport"
    highest_co2 = 0.0

    for item in summary.breakdown:
        if item.co2_kg > highest_co2:
            highest_co2 = item.co2_kg
            highest_category = item.category

    # Get top 3 tips for the highest-impact category
    tips = _TIPS_DATABASE.get(highest_category, [])[:3]

    # If category has fewer than 3 tips, pad with tips from other categories
    if len(tips) < 3:
        for category, category_tips in _TIPS_DATABASE.items():
            if category != highest_category:
                for tip in category_tips:
                    if tip not in tips:
                        tips.append(tip)
                    if len(tips) >= 3:
                        break
            if len(tips) >= 3:
                break

    # Estimate potential reduction (conservative: 30% of highest category)
    potential_reduction = round(highest_co2 * 0.3, 2)

    return InsightResponse(
        insights=tips,
        highest_impact_category=highest_category,
        potential_reduction_kg=potential_reduction,
    )
