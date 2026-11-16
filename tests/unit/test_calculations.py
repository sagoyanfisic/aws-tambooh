from backend.common.models.domain import Ingredient, PriceScenarioRequest
from backend.common.services.calculations import (
    consolidated_shopping,
    pen_to_usd,
    recipe_cost,
    simulate_scenario,
)


def item(name="Papa blanca", quantity=2):
    return Ingredient(
        product_id="papa",
        name=name,
        quantity_kg=quantity,
        price_pen_per_kg=4,
        calories_per_100g=77,
        protein_g_per_100g=2,
    )


def test_currency_and_cost():
    assert pen_to_usd(15) == 4.0
    assert recipe_cost([item()]) == 8


def test_inventory_deduction():
    assert consolidated_shopping([item()], ["Papa blanca"]) == []


def test_scenario_is_labeled():
    result = simulate_scenario(
        [{"product_id": "papa", "cost_pen": 10}], PriceScenarioRequest(changes_percent={"papa": 15})
    )
    assert result["is_simulation"] is True
    assert result["total_pen"] == 11.5
