# Data sources and provenance

Production adapters are import-based until an official source contract is verified. MIDAGRI prices, ENFEN context, INS nutrition, and INEI references must be imported from validated CSV/JSON exports and retain institution, URL/dataset ID, observation date, market, product, currency, price type, unit, original value, normalized value, and ingestion timestamp. `data/samples/prices.json` is demonstration data only.

## INS nutrition and recipes

The Peruvian Food Composition Tables (TPCA) are the planned nutrition reference: [INS repository record for the 11th edition](https://repositorio.ins.gob.pe/items/945f2705-5700-4561-9281-974adb816604). INS's [La Mejor Receta](https://lamejorreceta.ins.gob.pe/) is a separate recipe resource that describes its connection to food composition and price information. These pages are source references, not a machine-readable API contract. TamBooh currently has no validated import, product mapping or recipe catalog from them; therefore nutrition-backed meal recommendations are unavailable. Do not infer nutrient values or treat wholesale prices as household retail prices.

The INS repository lists the TPCA item as open access with a **CC BY-NC-ND 3.0 US** rights statement. Check those terms for the intended use before redistributing extracted records or transformed datasets; an open-access download does not by itself establish unrestricted reuse.

The import contract is `RecipeCatalog` in `backend/common/models/recipes.py`. Each recipe and ingredient carries its own source URL; nutrient fields require `basis=per_100g_edible_portion`, preparation state and INS edition. Unknown nutrient values remain `null`. `scripts/validate_recipe_catalog.py` accepts reviewed JSON and rejects duplicate recipe IDs, missing attribution, unsupported units/bases, and non-INS sources. It validates structure only; a qualified reviewer must still verify values and food/product mappings against the primary publications. No production catalog is included. The meal-plan endpoint remains unavailable until this catalog and compatible prices are configured.

