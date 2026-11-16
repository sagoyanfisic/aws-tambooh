"""Price access boundary. Production reads DynamoDB; demo data is opt-in only."""
import json
import os
from datetime import date
from pathlib import Path
from backend.common.models.domain import Ingredient, PriceRecord

class DataUnavailableError(RuntimeError):
    pass

def _sample_path() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "samples" / "prices.json"

class PriceRepository:
    def list_prices(self) -> list[PriceRecord]:
        if os.getenv("TAMBOOH_DATA_MODE", "dynamodb") == "demo":
            return self._demo_prices()
        table_name = os.getenv("PRICE_TABLE_NAME")
        if not table_name:
            raise DataUnavailableError("PRICE_TABLE_NAME is not configured")
        bucket = os.getenv("RAW_BUCKET")
        if not bucket:
            raise DataUnavailableError("RAW_BUCKET is not configured")
        import boto3
        from src.common.storage import load_published
        from src.common.models import slug
        from botocore.exceptions import BotoCoreError, ClientError
        try:
            records = load_published(boto3.resource("dynamodb").Table(table_name),
                                     boto3.client("s3"), bucket)
        except (BotoCoreError, ClientError, ValueError) as exc:
            raise DataUnavailableError("Published agricultural data is unavailable") from exc
        return [PriceRecord(
            product_id=slug(item.product), product_name=item.product, market=item.market,
            observation_date=item.observation_date, source_institution=item.institution,
            source_url=item.source_url, original_currency=item.currency,
            price_type=item.price_type, unit=item.unit_original,
            original_value=item.price_pen_per_unit, normalized_value=item.price_pen_per_kg,
            normalization_unit="kg" if item.price_pen_per_kg is not None else None,
            price_pen_per_l=item.price_pen_per_l,
            unit_original=item.unit_original, quality_flags=item.quality_flags,
            ingestion_timestamp=item.retrieved_at,
        ) for item in records]

    def latest_date(self, prices: list[PriceRecord]) -> date | None:
        return max((item.observation_date for item in prices), default=None)

    def ingredients(self, prices: list[PriceRecord]) -> list[Ingredient]:
        result = []
        for price in prices:
            if price.normalized_value is not None and price.normalized_value > 0:
                result.append(Ingredient(product_id=price.product_id, name=price.product_name,
                                         quantity_kg=1, price_pen_per_kg=price.normalized_value))
        return result

    def _demo_prices(self) -> list[PriceRecord]:
        payload = json.loads(_sample_path().read_text(encoding="utf-8"))
        return [PriceRecord.model_validate(item) for item in payload["records"]]
