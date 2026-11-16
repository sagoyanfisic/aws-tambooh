from collections import defaultdict
from typing import Iterable
from backend.common.models.domain import Ingredient, PriceScenarioRequest

PEN_PER_USD = 3.75

def pen_to_usd(value: float, rate: float = PEN_PER_USD) -> float:
    return round(value / rate, 2)

def recipe_cost(ingredients: Iterable[Ingredient]) -> float:
    return round(sum(i.quantity_kg * i.price_pen_per_kg for i in ingredients), 2)

def consolidated_shopping(ingredients: Iterable[Ingredient], pantry_items: list[str]) -> list[dict]:
    pantry = {item.strip().lower() for item in pantry_items}
    grouped = defaultdict(lambda: {"quantity_kg": 0.0, "cost_pen": 0.0})
    for item in ingredients:
        if item.name.lower() in pantry:
            continue
        grouped[item.name]["quantity_kg"] += item.quantity_kg
        grouped[item.name]["cost_pen"] += item.quantity_kg * item.price_pen_per_kg
    return [{"ingredient": name, "quantity_kg": round(v["quantity_kg"], 2), "cost_pen": round(v["cost_pen"], 2), "cost_usd": pen_to_usd(v["cost_pen"])} for name, v in sorted(grouped.items())]

def simulate_scenario(items: list[dict], request: PriceScenarioRequest) -> dict:
    projected = []
    total = 0.0
    for item in items:
        change = request.changes_percent.get(item["product_id"], 0.0)
        cost = round(item["cost_pen"] * (1 + change / 100), 2)
        total += cost
        projected.append({**item, "change_percent": change, "projected_cost_pen": cost})
    return {"is_simulation": True, "items": projected, "total_pen": round(total, 2), "total_usd": pen_to_usd(total), "budget_usd": request.budget_usd, "within_budget": pen_to_usd(total) <= request.budget_usd}

