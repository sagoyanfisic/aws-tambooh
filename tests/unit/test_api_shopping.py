import json
from datetime import date

from backend.common.models.domain import PriceRecord
from backend.functions.api import app


class FakePriceRepository:
    def list_prices(self):
        return [
            PriceRecord(
                product_id="papa-canchan",
                product_name="PAPA CANCHAN",
                market="GRAN MERCADO MAYORISTA DE LIMA",
                observation_date=date(2026, 11, 16),
                source_institution="MIDAGRI",
                source_url="http://example.test/report.pdf",
                price_type="wholesale",
                unit="kg",
                original_value=2.93,
                normalized_value=2.93,
                normalization_unit="kg",
            )
        ]


def call_api(monkeypatch, body):
    monkeypatch.setattr(app, "PriceRepository", FakePriceRepository)
    return app.lambda_handler(
        {
            "rawPath": "/api/v1/shopping-lists",
            "requestContext": {"http": {"method": "POST"}},
            "body": json.dumps(body),
        },
        None,
    )


def test_shopping_list_endpoint_returns_attributed_wholesale_estimate(monkeypatch):
    response = call_api(
        monkeypatch,
        {
            "items": [
                {
                    "product_id": "papa-canchan",
                    "market": "GRAN MERCADO MAYORISTA DE LIMA",
                    "source_url": "http://example.test/report.pdf",
                    "quantity_kg": 2,
                }
            ],
            "inventory": [
                {
                    "product_id": "papa-canchan",
                    "market": "GRAN MERCADO MAYORISTA DE LIMA",
                    "quantity_kg": 0.5,
                }
            ],
        },
    )
    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["items"][0]["quantity_to_buy_kg"] == 1.5
    assert payload["items"][0]["estimated_cost_pen"] == 4.4
    assert payload["items"][0]["source_institution"] == "MIDAGRI"
    assert payload["basis"] == "wholesale_reference"


def test_shopping_list_endpoint_rejects_empty_or_unpriced_request(monkeypatch):
    invalid = call_api(monkeypatch, {"items": []})
    assert invalid["statusCode"] == 400

    unavailable = call_api(
        monkeypatch,
        {
            "items": [
                {
                    "product_id": "lenteja",
                    "market": "GMML",
                    "source_url": "http://example.test/report.pdf",
                    "quantity_kg": 1,
                }
            ]
        },
    )
    assert unavailable["statusCode"] == 400
    assert "No hay un precio mayorista" in json.loads(unavailable["body"])["error"]["message"]


def test_scenario_endpoint_returns_pure_penn_simulation(monkeypatch):
    monkeypatch.setattr(app, "PriceRepository", FakePriceRepository)
    response = app.lambda_handler(
        {
            "rawPath": "/api/v1/price-scenarios",
            "requestContext": {"http": {"method": "POST"}},
            "body": json.dumps(
                {
                    "items": [
                        {
                            "product_id": "papa-canchan",
                            "market": "GRAN MERCADO MAYORISTA DE LIMA",
                            "source_url": "http://example.test/report.pdf",
                            "quantity_kg": 2,
                            "change_percent": 15,
                        }
                    ]
                }
            ),
        },
        None,
    )
    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["is_simulation"] is True
    assert payload["base_total_pen"] == 5.86
    assert payload["simulated_total_pen"] == 6.74
    assert payload["currency"] == "PEN"
    assert "pronóstico" in payload["notice"]


def test_meal_plan_refuses_unverified_recipe_and_nutrition_data(monkeypatch):
    monkeypatch.setattr(app, "PriceRepository", FakePriceRepository)
    response = app.lambda_handler(
        {
            "rawPath": "/api/v1/meal-plans",
            "requestContext": {"http": {"method": "POST"}},
            "body": json.dumps({"household_size": 4, "weekly_budget_usd": 65}),
        },
        None,
    )
    payload = json.loads(response["body"])
    assert response["statusCode"] == 503
    assert payload["error"]["code"] == "DATA_UNAVAILABLE"
    assert "source-attributed recipe catalog" in payload["error"]["message"]
    assert "nutritional references" in payload["error"]["message"]


def test_meal_plan_still_validates_request_before_reporting_missing_data(monkeypatch):
    monkeypatch.setattr(app, "PriceRepository", FakePriceRepository)
    response = app.lambda_handler(
        {
            "rawPath": "/api/v1/meal-plans",
            "requestContext": {"http": {"method": "POST"}},
            "body": json.dumps({"household_size": 0}),
        },
        None,
    )
    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"]["code"] == "VALIDATION_ERROR"
