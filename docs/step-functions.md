# Step Functions operations

SAM defines the Standard workflow `tambooh-<environment>-price-ingestion`. EventBridge Scheduler starts it daily at 07:00 America/Lima, configurable through `IngestionScheduleExpression`. Definition: `statemachine/ingest.asl.json`.

## Actual states

The `IngestSources` Map runs each source independently. Concurrency is deliberately one to honor the per-domain request interval shared by the two gob.pe sources. `PaceDomain` waits three seconds before `Fetch`. The downloader also paces every request within its invocation.

`Fetch` stores its result under `$.download`, preserving market and institution. `Downloaded` routes 404/unchanged results to `SourceSkipped`. Otherwise `Parse` receives the raw S3 key, hash, retrieval time and expected observation date. Parse validates, stages versioned records and snapshots, then publishes its manifest.

Each task catches source errors into `FetchFailed` or `ParseFailed`; other sources continue. SDK invocation failures retry three times with backoff. Network/HTTP retries happen inside the downloader, rather than multiplying source retries at both layers. Validation failures are not retried. The workflow deadline is 30 minutes.

`Report` sums rows, missing prices and failed sources. `RunStatus` sends a total source failure to `IngestionFailed`; partial failures are explicitly returned as `partial_failure`. A partial-failure execution completes successfully at the AWS workflow level, so operators must also inspect the summary.

## Run and inspect

```bash
aws stepfunctions start-execution --state-machine-arn <arn> --input file://events/ingestion.json
aws stepfunctions describe-execution --execution-arn <execution-arn>
aws stepfunctions get-execution-history --execution-arn <execution-arn>
```

A source item may include an explicit dated PDF URL. For backfill use `scripts/backfill.py`, which supplies the expected date to the worker; the daily workflow uses today's date in Lima.

Review failed source stage/error, CloudWatch structured logs, `RowsParsed`, `RowsMissing`, `SourceFailed`, and the Lambda Errors alarm. Log retention defaults to 14 days. The alarm changes state in CloudWatch; no email subscription is configured.

The active manifest contains `observation_date`, `retrieved_at`, `published_at`, hash, dataset ID and counts. Query `pk=DATASETS` consistently to inspect the last successful publication. Failed writes leave the previous manifest unchanged. Resolve validation/permissions problems and rerun; identical active bytes and parser versions are skipped.

Costs include state transitions, Lambda execution, logs/metrics, raw and snapshot S3 storage, DynamoDB operations and scheduled executions. Old unreferenced staging versions are retained; automated garbage collection is not implemented.
