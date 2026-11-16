from collections import defaultdict
from collections.abc import Iterable

from backend.common.models.domain import (
    Ingredient,
    PriceRecord,
    PriceScenarioRequest,
    ShoppingListRequest,
)

PEN_PER_USD = 3.75


def pen_to_usd(value: float, rate: float = PEN_PER_USD) -> float:
    return round(value / rate, 2)


def recipe_cost(ingredients: Iterable[Ingredient]) -> float:
    return round(sum(i.quantity_kg * i.price_pen_per_kg for i in ingredients), 2)


def build_shopping_list(prices: list[PriceRecord], request: ShoppingListRequest) -> dict:
    """Calculate quantities and PEN costs from published wholesale PEN/kg quotes."""
    latest: dict[tuple[str, str, str], PriceRecord] = {}
    for price in prices:
        identity = (price.product_id, price.market, price.source_url)
        previous = latest.get(identity)
        if previous is None or price.observation_date > previous.observation_date:
            latest[identity] = price

    wanted: dict[tuple[str, str, str], float] = defaultdict(float)
    for line in request.items:
        wanted[(line.product_id, line.market, line.source_url)] += line.quantity_kg

    inventory: dict[tuple[str, str], float] = defaultdict(float)
    for line in request.inventory:
        inventory[(line.product_id, line.market)] += line.quantity_kg

    result = []
    for quote_identity, needed in wanted.items():
        product_market = quote_identity[:2]
        price = latest.get(quote_identity)
        if (
            price is None
            or price.normalized_value is None
            or price.normalization_unit != "kg"
            or price.price_type != "wholesale"
            or "aves vivas" in price.market.casefold()
        ):
            raise ValueError(
                f"No hay un precio mayorista normalizado por kg para {quote_identity[0]} "
                f"en {quote_identity[1]} desde la fuente seleccionada."
            )
        in_pantry = inventory[product_market]
        to_buy = max(0.0, needed - in_pantry)
        result.append(
            {
                "product_id": price.product_id,
                "product_name": price.product_name,
                "market": price.market,
                "observation_date": price.observation_date,
                "source_institution": price.source_institution,
                "source_url": price.source_url,
                "quantity_needed_kg": round(needed, 3),
                "quantity_in_pantry_kg": round(in_pantry, 3),
                "quantity_to_buy_kg": round(to_buy, 3),
                "price_pen_per_kg": price.normalized_value,
                "estimated_cost_pen": round(to_buy * price.normalized_value, 2),
                "currency": "PEN",
                "price_type": "wholesale",
                "quality_flags": price.quality_flags,
            }
        )

    total = round(sum(line["estimated_cost_pen"] for line in result), 2)
    return {
        "items": result,
        "total_pen": total,
        "currency": "PEN",
        "basis": "wholesale_reference",
        "notice": (
            "Estimación con precios mayoristas por kg; no representa precio minorista "
            "ni incluye transporte, mermas o presentación comercial."
        ),
    }


def simulate_scenario(prices: list[PriceRecord], request: PriceScenarioRequest) -> dict:
    latest: dict[tuple[str, str, str], PriceRecord] = {}
    for price in prices:
        identity = (price.product_id, price.market, price.source_url)
        previous = latest.get(identity)
        if previous is None or price.observation_date > previous.observation_date:
            latest[identity] = price

    projected = []
    for line in request.items:
        price = latest.get((line.product_id, line.market, line.source_url))
        if (
            price is None
            or price.normalized_value is None
            or price.normalization_unit != "kg"
            or price.price_type != "wholesale"
            or "aves vivas" in price.market.casefold()
        ):
            raise ValueError(
                f"No hay un precio mayorista normalizado por kg para {line.product_id} "
                "en la fuente seleccionada."
            )
        base_cost = line.quantity_kg * price.normalized_value
        simulated_price = price.normalized_value * (1 + line.change_percent / 100)
        simulated_cost = line.quantity_kg * simulated_price
        projected.append(
            {
                "product_id": price.product_id,
                "product_name": price.product_name,
                "market": price.market,
                "source_institution": price.source_institution,
                "source_url": price.source_url,
                "observation_date": price.observation_date,
                "quantity_kg": round(line.quantity_kg, 3),
                "price_pen_per_kg": price.normalized_value,
                "simulated_price_pen_per_kg": round(simulated_price, 4),
                "base_cost_pen": round(base_cost, 2),
                "simulated_cost_pen": round(simulated_cost, 2),
                "difference_pen": round(simulated_cost - base_cost, 2),
                "change_percent": line.change_percent,
                "quality_flags": price.quality_flags,
            }
        )

    total_base = round(sum(item["base_cost_pen"] for item in projected), 2)
    total_simulated = round(sum(item["simulated_cost_pen"] for item in projected), 2)
    return {
        "is_simulation": True,
        "items": projected,
        "base_total_pen": total_base,
        "simulated_total_pen": total_simulated,
        "difference_pen": round(total_simulated - total_base, 2),
        "currency": "PEN",
        "basis": "hypothetical_price_simulation",
        "notice": "Escenario hipotético, no es pronóstico ni estimación validada.",
    }
