# API

Existing routes remain unchanged. `POST /api/v1/ai/explain` accepts `{ "question": "...", "facts": { ... } }`; Claude receives only those validated facts. If AI is disabled, it returns a deterministic explanation. Prices and budgets are calculated by Python services, not by Claude.

## Shopping list

`POST /api/v1/shopping-lists` requires each selected `product_id`, `market` and `source_url` so a quote cannot be silently substituted from another market or source. Quantities and pantry inventory are kilograms. The API includes only published wholesale quotes with a normalized PEN/kg value, subtracts inventory, and returns a PEN estimate with source and observation date for each item.

Example request:

```json
{
  "items": [
    {
      "product_id": "papa-canchan",
      "market": "GRAN MERCADO MAYORISTA DE LIMA",
      "source_url": "http://sistemas.midagri.gob.pe/sisap/intranet/mayoristas_lima/modulos/reporte_precios.pdf",
      "quantity_kg": 2
    }
  ],
  "inventory": [
    {
      "product_id": "papa-canchan",
      "market": "GRAN MERCADO MAYORISTA DE LIMA",
      "quantity_kg": 0.5
    }
  ]
}
```

The response marks `basis` as `wholesale_reference`. The estimate is not a retail grocery total and excludes transport, shrinkage and package sizes. Products from the live-bird market are excluded from household food calculations. It intentionally contains no USD conversion because no dated exchange-rate source is currently configured.

## Hypothetical price scenarios

`POST /api/v1/price-scenarios` accepts selected product quotes, quantities in kg and a percentage from -100% to 300%. Each quote must match its published product, market and source URL. The response includes the base and simulated PEN totals, observation date and source for every item, and sets `is_simulation: true` with a notice that the result is not a forecast. Live-bird prices and records without a trusted PEN/kg normalization are excluded.

Example request:

```json
{
  "items": [
    {
      "product_id": "papa-canchan",
      "market": "GRAN MERCADO MAYORISTA DE LIMA",
      "source_url": "http://sistemas.midagri.gob.pe/sisap/intranet/mayoristas_lima/modulos/reporte_precios.pdf",
      "quantity_kg": 2,
      "change_percent": 15
    }
  ]
}
```

Percentages are user-defined simulations. The API does not infer climate causes, generate forecasts or convert to USD.

## Meal plans

`POST /api/v1/meal-plans` validates household size, budget and preference fields, but currently returns `503 DATA_UNAVAILABLE`. A source-attributed recipe catalog, verified nutritional references, compatible published prices and a dated exchange-rate source are not yet configured. The endpoint intentionally does not return a hard-coded meal, inferred nutrient values or a USD budget comparison based on an undocumented exchange rate.

