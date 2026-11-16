from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PriceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: str
    product_name: str
    market: str
    observation_date: date
    source_institution: str
    source_url: str
    original_currency: str = "PEN"
    price_type: str = Field(pattern="^(wholesale|retail)$")
    unit: str
    original_value: float | None = Field(default=None, ge=0)
    normalized_value: float | None = Field(default=None, ge=0)
    unit_original: str | None = None
    normalization_unit: str | None = None
    price_pen_per_l: float | None = Field(default=None, ge=0)
    quality_flags: list[str] = Field(default_factory=list)
    ingestion_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Ingredient(BaseModel):
    product_id: str
    name: str
    quantity_kg: float = Field(gt=0)
    price_pen_per_kg: float = Field(gt=0)
    calories_per_100g: float | None = Field(default=None, ge=0)
    protein_g_per_100g: float | None = Field(default=None, ge=0)


class MealPlanRequest(BaseModel):
    household_size: int = Field(default=4, ge=1, le=20)
    weekly_budget_usd: float = Field(default=65, gt=0, le=10000)
    dietary_preferences: list[str] = []
    restricted_ingredients: list[str] = []
    pantry_items: list[str] = []


class PriceScenarioRequest(BaseModel):
    changes_percent: dict[str, float] = Field(min_length=1)
    budget_usd: float = Field(default=65, gt=0)
