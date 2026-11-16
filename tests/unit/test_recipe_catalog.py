import json

import pytest
from pydantic import ValidationError

from backend.common.models.recipes import RecipeCatalog
from scripts.validate_recipe_catalog import load_catalog

INS = "Instituto Nacional de Salud"


def sample_catalog():
    return {
        "schema_version": "1",
        "catalog_id": "test-catalog",
        "country": "PE",
        "recipes": [
            {
                "recipe_id": "test-recipe",
                "name": "Test recipe",
                "institution": INS,
                "source_url": "https://example.test/recipe",
                "servings": 2,
                "ingredients": [
                    {
                        "food_code": "TEST-1",
                        "food_name": "Test food",
                        "price_product_id": "test-food",
                        "quantity_g": 100,
                        "nutrition": {
                            "basis": "per_100g_edible_portion",
                            "preparation_state": "test-only raw sample",
                            "energy_kcal": None,
                            "protein_g": None,
                        },
                        "nutrition_source": {
                            "institution": INS,
                            "dataset": "test-only dataset",
                            "edition": "test edition",
                            "source_url": "https://example.test/nutrition",
                            "publication_date": None,
                        },
                    }
                ],
            }
        ],
    }


def test_recipe_catalog_requires_food_state_nutrient_basis_and_both_sources():
    catalog = RecipeCatalog.model_validate(sample_catalog())
    assert catalog.recipes[0].ingredients[0].nutrition.energy_kcal is None
    assert catalog.recipes[0].ingredients[0].nutrition.basis == "per_100g_edible_portion"
    assert str(catalog.recipes[0].source_url) == "https://example.test/recipe"


def test_recipe_catalog_rejects_unattributed_or_extra_data():
    payload = sample_catalog()
    payload["recipes"][0]["ingredients"][0]["nutrition"].pop("basis")
    with pytest.raises(ValidationError):
        RecipeCatalog.model_validate(payload)

    payload = sample_catalog()
    payload["recipes"][0]["invented_fact"] = "not accepted"
    with pytest.raises(ValidationError):
        RecipeCatalog.model_validate(payload)


def test_recipe_catalog_rejects_duplicate_recipe_ids():
    payload = sample_catalog()
    payload["recipes"].append(payload["recipes"][0].copy())
    catalog = RecipeCatalog.model_validate(payload)
    with pytest.raises(ValueError, match="duplicate recipe_id"):
        catalog.validate_unique_ids()


def test_import_validator_accepts_only_ins_recipe_and_nutrition_sources(tmp_path):
    input_file = tmp_path / "catalog.json"
    input_file.write_text(json.dumps(sample_catalog()), encoding="utf-8")
    assert load_catalog(input_file).catalog_id == "test-catalog"

    payload = sample_catalog()
    payload["recipes"][0]["ingredients"][0]["nutrition_source"]["institution"] = "Unverified"
    input_file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="must be INS"):
        load_catalog(input_file)
