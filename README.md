# TamBooh

TamBooh is a Peru-only serverless MVP for affordable meal planning and climate-resilience simulations. It keeps prices in PEN, converts to USD only with a dated illustrative rate, and labels local sample data and hypothetical scenarios clearly.

## Local run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest
cd frontend && npm install && npm run dev
```

The frontend is a self-contained demo. The Lambda handler is `backend.functions.api.app.lambda_handler`; invoke it with API Gateway HTTP API events or through SAM local. Claude is disabled by default.

## Deploy

Prerequisites: AWS CLI, SAM CLI, Python 3.12, Node 22, an AWS account, and a bootstrapped GitHub OIDC provider. Copy `samconfig.toml.example` to `samconfig.toml`, set a unique stack name, then run `sam build && sam deploy --guided` or `scripts/deploy.sh dev`. No deployment or production verification is claimed until those commands run in the target account.

See `docs/` for architecture, security, data provenance, costs, operations, and limitations.

## MIDAGRI wholesale ingestion

The new `src/` ingestion module fetches, parses, validates, and stores wholesale price publications from four MIDAGRI-related sources. It uses `statemachine/ingest.asl.json`, an arm64 Python 3.12 worker, S3 raw storage, DynamoDB normalized records, and an EventBridge Scheduler at 07:00 America/Lima. See [docs/price-ingestion.md](docs/price-ingestion.md) and `events/ingestion.json` for manual execution. SISAP Mañanero has no historical endpoint, so backfill is forward-only for that source.

