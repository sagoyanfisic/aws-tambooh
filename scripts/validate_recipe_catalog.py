#!/usr/bin/env python3
"""Validate and canonicalize a human-reviewed INS recipe catalog JSON file."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.common.models.recipes import RecipeCatalog

INS_NAME = "Instituto Nacional de Salud"


def load_catalog(path: Path) -> RecipeCatalog:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read valid JSON from {path}: {exc}") from exc
    try:
        catalog = RecipeCatalog.model_validate(raw).validate_unique_ids()
    except (ValidationError, ValueError) as exc:
        raise ValueError(f"Recipe catalog validation failed: {exc}") from exc

    non_ins = [
        recipe.recipe_id
        for recipe in catalog.recipes
        if recipe.institution != INS_NAME
        or any(item.nutrition_source.institution != INS_NAME for item in recipe.ingredients)
    ]
    if non_ins:
        raise ValueError(f"Recipe and nutrition sources must be INS; affected recipes: {non_ins}")
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Reviewed INS catalog JSON")
    parser.add_argument("--output", type=Path, help="Write validated canonical JSON")
    args = parser.parse_args()
    try:
        catalog = load_catalog(args.input)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    rendered = json.dumps(catalog.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Valid catalog: {len(catalog.recipes)} recipes written to {args.output}")
    else:
        print(f"Valid catalog: {len(catalog.recipes)} INS recipes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
