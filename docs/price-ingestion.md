# MIDAGRI wholesale price ingestion

The worker runs Python 3.12 on arm64. AWS inputs are validated by `IngestEvent`; only `fetch` and `parse` are accepted. Local text fixtures are available through `scripts/local_ingest.py`. Inline bodies and fixture inputs are rejected when AWS resource variables are configured.

## Download and discovery

- SISAP Mañanero uses its HTTP PDF URL. The recorded transport is `http_insecure`; HTTPS certificate checks remain enabled.
- GMML constructs dated SIEA file paths using the supplied observation date. In September it tries `set` and then `sep` if the first file returns 404. These are supplied source patterns, not proof of live publication.
- gob.pe discovery visits at most five HTML pages across collection, optional year collection, and matching month publication levels. It matches a PDF's exact date in its URL or anchor text, including encoded/numeric dates. No `sheet` pagination, SIEA directory listing or API endpoint is requested. It never substitutes an older observation for today's report.
- Unrecognized publication links require an explicit dated `source_url`; the worker does not fabricate a dataset.
- Official hosts are allow-listed, including redirect destinations. robots.txt must allow access. Requests are paced by domain at three seconds and retry transient network/429/5xx errors at most three attempts.
- robots.txt can redirect up to five times within the official host allow-list; HTTPS downgrades are rejected. An unreachable policy still blocks network acquisition. Errors now include the robots/document URL, HTTP status or transport exception so TLS/DNS/timeouts can be distinguished. No inference about geographic IP blocking is made from a generic connection failure.
- HTTP timeout is 10 seconds per operation, connect timeout 5 seconds, with a 110-second overall download budget. Lambda has 140 seconds and its task 150 seconds. Permanent HTTP errors are not retried.
- Download size is capped at 12 MiB. Raw PDFs must begin with `%PDF`.

## Preservation, parse and publication

1. Fetch stores raw bytes at `raw/<source>/YYYY/MM/DD/<sha256>.pdf` using an S3 conditional create. URL, hash, transport, HTTP status, retrieval time and Last-Modified are metadata.
2. Step Functions preserves source context and passes only S3 references. A 404 is `no_publication`; a previously active hash/parser version is `unchanged`.
3. Parse reads S3, verifies SHA-256 and extracts the PDF once using pdfplumber table cells. Headers determine columns; today's price, yesterday's price, seven-day average and previous-month average are distinct.
4. Unknown layouts, ambiguous headers, invalid prices, duplicates and empty datasets fail validation. Missing `:` remains null. Unexpected formats never return a successful zero-row publication.
5. Prices normalize only with a known unit equivalence. A ten-package bundle of 1 kg is 10 kg; bottles, dozens and bundles have no inferred mass. Liter prices have a separate field.
6. DynamoDB receives Decimal-compatible rows, then S3 receives complete CSV and JSON snapshots. A conditional manifest update makes the version active only after all writes finish. A concurrent publication conflict fails without replacing the competing version.
7. API reads strongly consistent active manifests and complete S3 snapshots. It does not scan staging rows. Missing or unsupported nutrition stays unknown.

DynamoDB preserves the existing lowercase `pk/sk` table schema. Price row keys are `PRODUCT#<product-variety-unit>#MARKET#<market>` and `DATE#<day>#SRC#<source>#VERSION#<dataset>`. GSI1 groups historical rows by date. The version is derived from the source hash and parser version. Manifests use `pk=DATASETS`, `sk=SOURCE#<source>`. New historical imports store their snapshot without replacing a more recent active observation.

Curated paths are `curated/prices/source=<source>/date=<day>/version=<dataset>/part.csv` and `records.json`. Raw files expire after 90 days; curated snapshots do not share that lifecycle rule. No historical row is deleted by an ingestion retry.

## Local use

```bash
python scripts/local_ingest.py --source sisap_mananero
python scripts/local_ingest.py --source sisap_mananero --file /tmp/report.pdf --date 2026-11-14
python scripts/backfill.py --source gmml_ingreso --from 2026-11-13 --to 2026-11-14
```

The local runner refuses AWS resource variables. Backfill uses each requested date for source discovery and validation; Mañanero has no historical endpoint and is rejected for backfill. Without AWS resource variables, backfill validates locally; with configured resources it can write to AWS and therefore requires deployment/operator authorization.

## Manual official PDF import from S3

Use this when an operator can obtain an official PDF but the source is inaccessible from Lambda. This is an explicit file import, not a successful live network download. The operator must verify the file's institution, source URL, market, wholesale units and observation date before uploading it. The pipeline verifies PDF structure, extracted date, table layout and values; it cannot authenticate the original publisher's bytes simply from a declared URL.

1. Deploy the revised template and worker. The worker gains read-only access to `imports/*` in its own raw bucket. Normal raw/curated permissions remain separate.
2. Download and inspect an official PDF using an authorized client. Keep the real source URL and date; never disable TLS certificate verification. A previously downloaded SISAP file is a historical import, not a newly fetched report.
3. Upload it to the deployed raw bucket at `imports/sisap_mananero/reporte_precios.pdf` (or `imports/<other source_id>/...`). No other bucket is accepted by the worker.
4. Copy `events/ingestion-s3.example.json` into a new Step Functions execution. **Replace its example date with the date printed inside your PDF** and set its source URL, source ID, market and institution to the actual document. `expected_observation_date` is required for imports. The normal `events/ingestion.json` remains the scheduled network workflow input.
5. Fetch reads the S3 object, checks `%PDF` and size, and preserves a SHA-256 copy under `raw/`. Metadata records `acquisition=manual_s3_import` and `http-status=not-requested`. It does not contact the source or claim an HTTP response.
6. Parse reads that raw reference, requires the PDF's date to match the declared observation, then uses the same validation, normalized records and atomic publication logic as network acquisition. Unsupported real table layouts still fail closed. Check each source's rows and errors, then verify `/api/v1/prices`.

The Map state passes each source object intact so manual references and explicit historical dates reach Fetch. It continues to pass only raw references and hashes into Parse; PDFs never enter the state-machine payload. A source import is an AWS operator action and is not exposed through a public administrative endpoint.

An initial deployed run failed before parsing: SISAP and SIEA exhausted retries on robots.txt, while the two gob.pe sources had no matching dated link within the earlier two-level search. That evidence does not establish an IP filter, absent publication, or working PDF parser for the current official layout. New discovery, better diagnostics and S3 imports are locally tested until redeployed and run with a real file.

## Verification boundaries

Text fixtures and mocked PDF table extraction test validation and column mapping. Source discovery tests use simulated official pages. They are not official PDF fixtures. Real source layouts, accessibility from us-east-2 and native arm64 package installation still require verification with reachable official files and a working package registry. An unsupported real layout fails closed and requires a source-specific adapter. There is no claim that all four live PDFs are already verified.
