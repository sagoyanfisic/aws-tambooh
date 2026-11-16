# API

Existing routes remain unchanged. `POST /api/v1/ai/explain` accepts `{ "question": "...", "facts": { ... } }`; Claude receives only those validated facts. If AI is disabled, it returns a deterministic explanation. Prices and budgets are calculated by Python services, not by Claude.

