import pytest
from pydantic import ValidationError

from backend.common.models.domain import MealPlanRequest, PriceScenarioRequest


def test_household_bounds():
    with pytest.raises(ValidationError):
        MealPlanRequest(household_size=0)


def test_price_scenario_bounds_and_requires_product_selection():
    with pytest.raises(ValidationError):
        PriceScenarioRequest(items=[])
    with pytest.raises(ValidationError):
        PriceScenarioRequest(
            items=[
                {
                    "product_id": "papa",
                    "market": "GMML",
                    "source_url": "https://example.test/p.pdf",
                    "quantity_kg": 1,
                    "change_percent": -101,
                }
            ]
        )
