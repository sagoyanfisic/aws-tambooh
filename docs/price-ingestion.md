# MIDAGRI wholesale price ingestion

The ingestion module is under `src/`, uses Python 3.12 on arm64, and is orchestrated by the Standard Step Functions definition in `statemachine/ingest.asl.json`. A daily EventBridge Scheduler execution at 07:00 `America/Lima` sends four source descriptors. Each source runs independently in a Map state; a source failure is reported without preventing the other sources from completing.

SISAP Mañanero is intentionally configured with its documented HTTP URL and recorded as `http_insecure`. The worker sends an identifiable User-Agent, accepts PDF responses, uses a 60-second timeout, and retries three times with exponential backoff. It does not use an unverified HTTPS fallback (`verify=False`/`CERT_NONE` is forbidden). TLS verification remains enabled for HTTPS sources. The other sources use the official SIEA and gob.pe collection URLs as discovery roots; adapters must be updated with the exact dated PDF link when the daily publication is identified. No scraping of SIEA directory listings or `api/` endpoints is performed.

For a live response, the worker requires the `%PDF` signature and extracts the Spanish observation date from the document. Non-fixture SISAP reports are rejected when their observation date is not the current UTC/Lima processing date. An HTTP 500, DNS error, timeout, non-PDF response, or stale report is a source failure; the Step Functions Map continues with the other sources. A real AWS probe should be run from a Lambda in `us-east-1` because local success does not prove that MIDAGRI accepts AWS-origin IPs. The probe event is `events/sisap-probe.json`; it must not be invoked without AWS deployment authorization.

Raw bytes are stored under `raw/<source_id>/YYYY/MM/DD/` with URL, hash, HTTP status, and retrieval metadata. Normalized records use DynamoDB keys `PRODUCT#<slug>#MARKET#<slug>` and `DATE#YYYY-MM-DD#SRC#<source_id>`, with GSI1 for day queries. Curated output is CSV under `curated/prices/source=<id>/date=YYYY-MM-DD/part.csv`; CSV is used in the MVP to avoid a native Parquet dependency.

Local parser tests use clearly labeled text fixtures that represent extracted PDF tables. Real PDF fixtures should be added to `tests/fixtures/` when the source is reachable from the development environment; PDF parsing uses `pdfplumber` and does not fabricate missing values.

Manual local invocation:

```bash
sam local invoke PriceWorkerFunction -e events/ingestion.json
aws stepfunctions start-execution --state-machine-arn <arn> --input file://events/ingestion.json
```

