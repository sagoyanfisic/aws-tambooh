from datetime import date

import pytest

from backend.common.models.domain import (
    Ingredient,
    PriceRecord,
    PriceScenarioRequest,
    ShoppingListRequest,
)
from backend.common.services.calculations import (
    build_shopping_list,
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


def wholesale(product_id="papa-canchan", market="GMML", value=2.93):
    return PriceRecord(
        product_id=product_id,
        product_name="PAPA CANCHAN",
        market=market,
        observation_date=date(2026, 11, 16),
        source_institution="MIDAGRI",
        source_url="http://example.test/report.pdf",
        price_type="wholesale",
        unit="kg",
        original_value=value,
        normalized_value=value,
        normalization_unit="kg",
    )


def test_shopping_deducts_quantity_inventory_and_uses_pen_only():
    request = ShoppingListRequest(
        items=[
            {
                "product_id": "papa-canchan",
                "market": "GMML",
                "source_url": "http://example.test/report.pdf",
                "quantity_kg": 3,
            }
        ],
        inventory=[{"product_id": "papa-canchan", "market": "GMML", "quantity_kg": 1.25}],
    )
    result = build_shopping_list([wholesale()], request)
    assert result["items"][0]["quantity_to_buy_kg"] == 1.75
    assert result["items"][0]["estimated_cost_pen"] == 5.13
    assert result["total_pen"] == 5.13
    assert result["currency"] == "PEN"
    assert result["basis"] == "wholesale_reference"
    assert "total_usd" not in result


def test_shopping_never_uses_other_market_and_requires_kg_normalization():
    request = ShoppingListRequest(
        items=[
            {
                "product_id": "papa-canchan",
                "market": "otro",
                "source_url": "http://example.test/report.pdf",
                "quantity_kg": 1,
            }
        ]
    )
    with pytest.raises(ValueError, match="No hay un precio mayorista"):
        build_shopping_list([wholesale()], request)

    unnormalized = wholesale()
    unnormalized.normalization_unit = None
    request.items[0].market = "GMML"
    with pytest.raises(ValueError, match="normalizado por kg"):
        build_shopping_list([unnormalized], request)

    live_bird = wholesale(market="MERCADO MAYORISTA DE AVES VIVAS")
    request.items[0].market = live_bird.market
    with pytest.raises(ValueError, match="No hay un precio mayorista"):
        build_shopping_list([live_bird], request)


def test_shopping_combines_repeated_requested_and_inventory_quantities():
    request = ShoppingListRequest(
        items=[
            {
                "product_id": "papa-canchan",
                "market": "GMML",
                "source_url": "http://example.test/report.pdf",
                "quantity_kg": 1,
            },
            {
                "product_id": "papa-canchan",
                "market": "GMML",
                "source_url": "http://example.test/report.pdf",
                "quantity_kg": 2,
            },
        ],
        inventory=[
            {"product_id": "papa-canchan", "market": "GMML", "quantity_kg": 0.25},
            {"product_id": "papa-canchan", "market": "GMML", "quantity_kg": 0.25},
        ],
    )
    result = build_shopping_list([wholesale()], request)
    assert len(result["items"]) == 1
    assert result["items"][0]["quantity_needed_kg"] == 3
    assert result["items"][0]["quantity_in_pantry_kg"] == 0.5
    assert result["items"][0]["quantity_to_buy_kg"] == 2.5


def test_shopping_selects_the_explicit_source_when_market_quotes_overlap():
    selected_source = "https://example.test/second.pdf"
    request = ShoppingListRequest(
        items=[
            {
                "product_id": "papa-canchan",
                "market": "GMML",
                "source_url": selected_source,
                "quantity_kg": 1,
            }
        ]
    )
    result = build_shopping_list(
        [wholesale(value=2), wholesale(value=3).model_copy(update={"source_url": selected_source})],
        request,
    )
    assert result["items"][0]["source_url"] == selected_source
    assert result["items"][0]["estimated_cost_pen"] == 3


def test_scenario_is_labeled():
    request = PriceScenarioRequest(
        items=[
            {
                "product_id": "papa-canchan",
                "market": "GMML",
                "source_url": "http://example.test/report.pdf",
                "quantity_kg": 2,
                "change_percent": 15,
            }
        ]
    )
    result = simulate_scenario([wholesale()], request)
    assert result["is_simulation"] is True
    assert result["base_total_pen"] == 5.86
    assert result["simulated_total_pen"] == 6.74
    assert result["difference_pen"] == 0.88
    assert result["currency"] == "PEN"
    assert result["basis"] == "hypothetical_price_simulation"
    assert "pronóstico" in result["notice"]
