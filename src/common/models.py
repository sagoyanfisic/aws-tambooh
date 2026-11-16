from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SourceId = Literal["sisap_mananero", "gmml_ingreso", "papa_boletin", "productores"]


class PriceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    observation_date: date
    retrieved_at: datetime
    source_id: SourceId
    source_url: str
    institution: str
    transport: Literal["https", "http_insecure"]
    market: str
    category: str | None = None
    product: str
    variety_or_brand: str | None = None
    price_type: Literal["wholesale"] = "wholesale"
    unit_original: str
    unit_qty_kg: float | None = Field(default=None, gt=0)
    unit_qty_l: float | None = Field(default=None, gt=0)
    price_pen_per_unit: float | None = Field(default=None, ge=0)
    price_pen_per_kg: float | None = Field(default=None, ge=0)
    price_pen_per_l: float | None = Field(default=None, ge=0)
    price_prev_day: float | None = Field(default=None, ge=0)
    avg_7d: float | None = Field(default=None, ge=0)
    avg_prev_month: float | None = Field(default=None, ge=0)
    volume_t: float | None = Field(default=None, ge=0)
    currency: Literal["PEN"] = "PEN"
    is_missing: bool = False
    quality_flags: list[str] = Field(default_factory=list)
    raw_s3_key: str = ""
    parser_version: str = "2.0.0"

    @model_validator(mode="after")
    def validate_record(self):
        if not self.product.strip() or not self.market.strip() or not self.unit_original.strip():
            raise ValueError("product, market and unit are required")
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must include its timezone")
        if self.is_missing != (self.price_pen_per_unit is None):
            raise ValueError("is_missing must match the original price")
        return self

    @property
    def product_slug(self) -> str:
        return slug(self.product)

    @property
    def market_slug(self) -> str:
        return slug(self.market)


def slug(value: str) -> str:
    import re
    import unicodedata

    clean = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", clean).strip("-") or "unknown"


def dynamo_keys(record: PriceRecord, dataset_id: str = "") -> dict[str, str]:
    identity = slug(f"{record.product} {record.variety_or_brand or ''} {record.unit_original}")
    suffix = f"#VERSION#{dataset_id}" if dataset_id else ""
    return {
        "pk": f"PRODUCT#{identity}#MARKET#{record.market_slug}",
        "sk": f"DATE#{record.observation_date.isoformat()}#SRC#{record.source_id}{suffix}",
        "GSI1PK": f"DATE#{record.observation_date.isoformat()}",
        "GSI1SK": f"SRC#{record.source_id}#PRODUCT#{identity}#MARKET#{record.market_slug}{suffix}",
    }
