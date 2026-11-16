"""Validated, source-attributed recipe and food-composition import contracts."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class NutritionSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution: str = Field(min_length=2, max_length=200)
    dataset: str = Field(min_length=2, max_length=240)
    edition: str = Field(min_length=1, max_length=80)
    source_url: HttpUrl
    publication_date: date | None = None


class NutritionFactsPer100g(BaseModel):
    model_config = ConfigDict(extra="forbid")

    basis: Literal["per_100g_edible_portion"]
    preparation_state: str = Field(min_length=2, max_length=120)
    energy_kcal: float | None = Field(default=None, ge=0, le=1000)
    protein_g: float | None = Field(default=None, ge=0, le=100)
    carbohydrate_g: float | None = Field(default=None, ge=0, le=100)
    fat_g: float | None = Field(default=None, ge=0, le=100)
    fiber_g: float | None = Field(default=None, ge=0, le=100)


class RecipeIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    food_code: str = Field(min_length=1, max_length=80)
    food_name: str = Field(min_length=2, max_length=240)
    price_product_id: str = Field(min_length=1, max_length=160)
    quantity_g: float = Field(gt=0, le=100_000)
    nutrition: NutritionFactsPer100g
    nutrition_source: NutritionSource


class ValidatedRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=2, max_length=240)
    institution: str = Field(min_length=2, max_length=200)
    source_url: HttpUrl
    source_date: date | None = None
    servings: int = Field(gt=0, le=100)
    ingredients: list[RecipeIngredient] = Field(min_length=1, max_length=100)
    dietary_tags: list[str] = Field(default_factory=list, max_length=30)


class RecipeCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]
    catalog_id: str = Field(min_length=1, max_length=120)
    country: Literal["PE"]
    recipes: list[ValidatedRecipe] = Field(min_length=1, max_length=1000)

    def validate_unique_ids(self) -> "RecipeCatalog":
        ids = [recipe.recipe_id for recipe in self.recipes]
        if len(ids) != len(set(ids)):
            raise ValueError("Recipe catalog contains duplicate recipe_id values")
        return self
