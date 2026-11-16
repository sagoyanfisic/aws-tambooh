import json
import logging

from botocore.exceptions import BotoCoreError, ClientError

from backend.common.models.domain import MealPlanRequest, PriceScenarioRequest
from backend.common.repositories.price_repository import DataUnavailableError, PriceRepository
from backend.common.services.ai import AIProvider
from backend.common.services.calculations import (
    consolidated_shopping,
    pen_to_usd,
    recipe_cost,
    simulate_scenario,
)
from backend.common.utils.http import parse_json, response

logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    path = event.get("rawPath", event.get("path", "/api/v1/health"))
    method = (
        event.get("requestContext", {})
        .get("http", {})
        .get("method", event.get("httpMethod", "GET"))
    )
    repository = PriceRepository()
    try:
        if path.endswith("/health"):
            return response(
                200,
                {
                    "status": "ok",
                    "service": "tambooh",
                    "data_source": "demo"
                    if __import__("os").getenv("TAMBOOH_DATA_MODE") == "demo"
                    else "dynamodb",
                },
            )
        prices = repository.list_prices()
        if path.endswith("/products"):
            return response(200, {"items": [p.model_dump() for p in prices], "count": len(prices)})
        if path.endswith("/prices/trends"):
            return response(200, {"items": [], "status": "insufficient_history"})
        if path.endswith("/prices"):
            return response(
                200,
                {
                    "items": [p.model_dump() for p in prices],
                    "currency": "PEN",
                    "last_updated": str(repository.latest_date(prices)) if prices else None,
                },
            )
        if path.endswith("/meal-plans") and method == "POST":
            request = parse_json(event, MealPlanRequest)
            base = repository.ingredients(prices)
            portions = {"papa": 1.0, "arroz": 0.8, "lenteja": 0.5, "pollo": 0.6, "zanahoria": 0.4}
            selected = [
                i.model_copy(update={"quantity_kg": q * request.household_size / 4})
                for i in base
                for key, q in portions.items()
                if i.product_id == key
            ]
            if {i.product_id for i in selected} != set(portions):
                raise DataUnavailableError(
                    "Recipe catalog mapping or compatible ingredient prices are missing"
                )
            cost = recipe_cost(selected)
            source_label = (
                "TamBooh demo dataset (not official market data)"
                if __import__("os").getenv("TAMBOOH_DATA_MODE") == "demo"
                else "DynamoDB published agricultural dataset"
            )
            return response(
                200,
                {
                    "household_size": request.household_size,
                    "weekly_budget_usd": request.weekly_budget_usd,
                    "estimated_cost_pen": cost,
                    "estimated_cost_usd": pen_to_usd(cost),
                    "within_budget": pen_to_usd(cost) <= request.weekly_budget_usd,
                    "meals": [
                        {
                            "name": "Lentejas con arroz y ensalada",
                            "ingredients": [i.model_dump() for i in selected],
                            "reason": "Combines affordable local staples with protein and fiber.",
                        }
                    ],
                    "source_attribution": [source_label],
                },
            )
        if path.endswith("/shopping-lists") and method == "POST":
            request = parse_json(event, MealPlanRequest)
            base = repository.ingredients(prices)
            selected = [
                i.model_copy(update={"quantity_kg": 0.25 * request.household_size / 4})
                for i in base
            ]
            if not selected:
                raise DataUnavailableError("No compatible kilogram prices available")
            items = consolidated_shopping(selected, request.pantry_items)
            return response(
                200,
                {
                    "items": items,
                    "total_pen": round(sum(x["cost_pen"] for x in items), 2),
                    "total_usd": round(sum(x["cost_usd"] for x in items), 2),
                    "currency_rate": {"pen_per_usd": 3.75, "as_of": "2026-11-10"},
                },
            )
        if path.endswith("/price-scenarios") and method == "POST":
            req = parse_json(event, PriceScenarioRequest)
            items = [
                {
                    "product_id": p.product_id,
                    "ingredient": p.product_name,
                    "quantity_kg": 1,
                    "cost_pen": p.normalized_value,
                }
                for p in prices
                if p.normalized_value is not None
            ]
            if not items:
                raise DataUnavailableError("No compatible kilogram prices available")
            return response(200, simulate_scenario(items, req))
        if path.endswith("/food-reserves") and method == "POST":
            request = parse_json(event, MealPlanRequest)
            days = 7
            return response(
                200,
                {
                    "household_size": request.household_size,
                    "reserve_days": days,
                    "recommended_staple_kg": round(request.household_size * days * 0.18, 2),
                    "method": "illustrative household reserve calculation",
                    "source_attribution": ["TamBooh deterministic planning rule"],
                },
            )
        if path.endswith("/ai/explain") and method == "POST":
            payload = json.loads(event.get("body") or "{}")
            if not isinstance(payload.get("question", ""), str) or not isinstance(
                payload.get("facts", {}), dict
            ):
                raise ValueError("question must be text and facts must be an object")
            return response(
                200,
                AIProvider().explain(
                    payload.get("question", "Explain this plan"), payload.get("facts", {})
                ),
            )
        return response(404, {"error": {"code": "NOT_FOUND", "message": "Route not found"}})
    except DataUnavailableError as exc:
        return response(503, {"error": {"code": "DATA_UNAVAILABLE", "message": str(exc)}})
    except ValueError as exc:
        return response(400, {"error": {"code": "VALIDATION_ERROR", "message": str(exc)}})
    except (BotoCoreError, ClientError, OSError, RuntimeError, TypeError, KeyError) as exc:
        logger.error("api_request_failed", extra={"error_type": type(exc).__name__})
        return response(500, {"error": {"code": "INTERNAL_ERROR", "message": "Unexpected error"}})
