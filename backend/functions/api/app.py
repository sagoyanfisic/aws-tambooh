import json
import logging

from botocore.exceptions import BotoCoreError, ClientError

from backend.common.models.domain import (
    MealPlanRequest,
    PriceScenarioRequest,
    ShoppingListRequest,
)
from backend.common.repositories.price_repository import DataUnavailableError, PriceRepository
from backend.common.services.ai import AIProvider
from backend.common.services.calculations import (
    build_shopping_list,
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
            parse_json(event, MealPlanRequest)
            raise DataUnavailableError(
                "Meal planning is unavailable until a source-attributed recipe catalog, "
                "verified nutritional references, and compatible published prices are configured."
            )
        if path.endswith("/shopping-lists") and method == "POST":
            request = parse_json(event, ShoppingListRequest)
            return response(200, build_shopping_list(prices, request))
        if path.endswith("/price-scenarios") and method == "POST":
            req = parse_json(event, PriceScenarioRequest)
            return response(200, simulate_scenario(prices, req))
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
