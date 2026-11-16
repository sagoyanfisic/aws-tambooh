# Operations

Check Step Functions execution status, `last_successful_update`, rejected record counts, Lambda errors, and dataset age. A failed ingestion does not replace the active dataset. For a stale dataset, inspect the source file, validation error, S3 permissions, and DynamoDB write errors before rerunning manually. Do not put household or API-key data in logs.

