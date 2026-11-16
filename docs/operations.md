# Operations

Check the Step Functions summary (including partial_failure), active manifest published_at/observation_date, RowsParsed, RowsMissing, SourceFailed, Lambda errors and dataset age. A failed ingestion does not replace the active dataset. For a stale dataset, inspect the source file, validation error, S3 permissions and DynamoDB write errors before rerunning. The CloudWatch Lambda Errors alarm has no email subscription. See step-functions.md for exact states and manual commands. Do not put household or API-key data in logs.

