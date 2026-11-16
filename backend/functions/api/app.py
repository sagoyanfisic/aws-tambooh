import json
from backend.common.repositories.sample_data import PRICES, ingredients
from backend.common.models.domain import MealPlanRequest, PriceScenarioRequest
from backend.common.services.calculations import consolidated_shopping, pen_to_usd, recipe_cost, simulate_scenario
from backend.common.services.ai import AIProvider
from backend.common.utils.http import response, parse_json

def lambda_handler(event, context):
    path = event.get("rawPath", event.get("path", "/api/v1/health"))
    method = event.get("requestContext", {}).get("http", {}).get("method", event.get("httpMethod", "GET"))
    try:
        if path.endswith("/health"):
            return response(200, {"status": "ok", "service": "tambooh", "data_last_updated": str(PRICES[0].observation_date)})
        if path.endswith("/products"):
            return response(200, {"items": [p.model_dump() for p in PRICES], "count": len(PRICES)})
        if path.endswith("/prices/trends"):
            return response(200, {"items": [{"product_id": p.product_id, "direction": "stable", "change_percent": 0.0, "source": p.source_url} for p in PRICES]})
        if path.endswith("/prices"):
            return response(200, {"items": [p.model_dump() for p in PRICES], "currency": "PEN", "source_note": "Clearly labeled local sample data"})
        if path.endswith("/meal-plans") and method == "POST":
            request = parse_json(event, MealPlanRequest)
            base = ingredients()
            portions = {"papa": 1.0, "arroz": 0.8, "lenteja": 0.5, "pollo": 0.6, "zanahoria": 0.4}
            selected = [i.model_copy(update={"quantity_kg": q * request.household_size / 4}) for i in base for key, q in portions.items() if i.product_id == key]
            cost = recipe_cost(selected)
            return response(200, {"household_size": request.household_size, "weekly_budget_usd": request.weekly_budget_usd, "estimated_cost_pen": cost, "estimated_cost_usd": pen_to_usd(cost), "within_budget": pen_to_usd(cost) <= request.weekly_budget_usd, "meals": [{"name": "Lentejas con arroz y ensalada", "ingredients": [i.model_dump() for i in selected], "reason": "Combines affordable local staples with protein and fiber."}], "source_attribution": ["MIDAGRI sample price dataset", "INS-compatible nutrition reference sample"]})
        if path.endswith("/shopping-lists") and method == "POST":
            request = parse_json(event, MealPlanRequest)
            base = ingredients(); selected = [i.model_copy(update={"quantity_kg": 0.25 * request.household_size / 4}) for i in base]
            items = consolidated_shopping(selected, request.pantry_items)
            return response(200, {"items": items, "total_pen": round(sum(x["cost_pen"] for x in items), 2), "total_usd": round(sum(x["cost_usd"] for x in items), 2), "currency_rate": {"pen_per_usd": 3.75, "as_of": "2026-11-10"}})
        if path.endswith("/price-scenarios") and method == "POST":
            req = parse_json(event, PriceScenarioRequest)
            items = [{"product_id": p.product_id, "ingredient": p.product_name, "quantity_kg": 1, "cost_pen": p.normalized_value} for p in PRICES]
            return response(200, simulate_scenario(items, req))
        if path.endswith("/food-reserves") and method == "POST":
            request = parse_json(event, MealPlanRequest)
            days = 7
            return response(200, {"household_size": request.household_size, "reserve_days": days, "recommended_staple_kg": round(request.household_size * days * 0.18, 2), "method": "illustrative household reserve calculation", "source_attribution": ["TamBooh deterministic planning rule"]})
        if path.endswith("/ai/explain") and method == "POST":
            payload = json.loads(event.get("body") or "{}")
            if not isinstance(payload.get("question", ""), str) or not isinstance(payload.get("facts", {}), dict):
                raise ValueError("question must be text and facts must be an object")
            return response(200, AIProvider().explain(payload.get("question", "Explain this plan"), payload.get("facts", {})))
        return response(404, {"error": {"code": "NOT_FOUND", "message": "Route not found"}})
    except ValueError as exc:
        return response(400, {"error": {"code": "VALIDATION_ERROR", "message": str(exc)}})
    except Exception:
        return response(500, {"error": {"code": "INTERNAL_ERROR", "message": "Unexpected error"}})

