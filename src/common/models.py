from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field

SourceId = Literal["sisap_mananero", "gmml_ingreso", "papa_boletin", "productores"]

class PriceRecord(BaseModel):
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
    price_prev_day: float | None = Field(default=None, ge=0)
    avg_7d: float | None = Field(default=None, ge=0)
    avg_prev_month: float | None = Field(default=None, ge=0)
    volume_t: float | None = Field(default=None, ge=0)
    currency: Literal["PEN"] = "PEN"
    is_missing: bool = False
    quality_flags: list[str] = []
    raw_s3_key: str = ""
    parser_version: str = "1.0.0"

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

def dynamo_keys(record: PriceRecord) -> dict[str, str]:
    return {"PK": f"PRODUCT#{record.product_slug}#MARKET#{record.market_slug}", "SK": f"DATE#{record.observation_date.isoformat()}#SRC#{record.source_id}", "GSI1PK": f"DATE#{record.observation_date.isoformat()}", "GSI1SK": f"SRC#{record.source_id}#PRODUCT#{record.product_slug}"}

