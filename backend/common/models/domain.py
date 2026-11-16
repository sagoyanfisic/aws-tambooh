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


class ShoppingLineRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=160)
    market: str = Field(min_length=1, max_length=240)
    source_url: str = Field(min_length=1, max_length=2048)
    quantity_kg: float = Field(gt=0, le=1000)


class InventoryLineRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=160)
    market: str = Field(min_length=1, max_length=240)
    quantity_kg: float = Field(ge=0, le=1000)


class ShoppingListRequest(BaseModel):
    items: list[ShoppingLineRequest] = Field(min_length=1, max_length=100)
    inventory: list[InventoryLineRequest] = Field(default_factory=list, max_length=100)


class PriceScenarioLineRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=160)
    market: str = Field(min_length=1, max_length=240)
    source_url: str = Field(min_length=1, max_length=2048)
    quantity_kg: float = Field(gt=0, le=1000)
    change_percent: float = Field(ge=-100, le=300)


class PriceScenarioRequest(BaseModel):
    items: list[PriceScenarioLineRequest] = Field(min_length=1, max_length=100)
