# MIDAGRI wholesale price ingestion

The worker runs Python 3.12 on arm64. AWS inputs are validated by `IngestEvent`; only `fetch` and `parse` are accepted. Local text fixtures are available through `scripts/local_ingest.py`. Inline bodies and fixture inputs are rejected when AWS resource variables are configured.

## Download and discovery

- SISAP Mañanero uses its HTTP PDF URL. The recorded transport is `http_insecure`; HTTPS certificate checks remain enabled.
- GMML constructs dated SIEA file paths using the supplied observation date. In September it tries `set` and then `sep` if the first file returns 404. These are supplied source patterns, not proof of live publication.
- gob.pe discovery visits the collection and at most two matching month/date publication pages, then follows a dated PDF link. No `?sheet=`, SIEA directory listing or API endpoint is requested.
- Unrecognized publication links require an explicit dated `source_url`; the worker does not fabricate a dataset.
- Official hosts are allow-listed, including redirect destinations. robots.txt must allow access. Requests are paced by domain at three seconds and retry transient network/429/5xx errors at most three attempts.
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

## Verification boundaries

Text fixtures and mocked PDF table extraction test validation and column mapping. Source discovery tests use simulated official pages. They are not official PDF fixtures. Real source layouts, accessibility from us-east-1 and native arm64 package installation still require verification with reachable official files and a working package registry. An unsupported real layout fails closed and requires a source-specific adapter. There is no claim that all four live PDFs are already verified.
