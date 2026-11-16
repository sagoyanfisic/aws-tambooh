# Step Functions

The Standard workflow `tambooh-price-ingestion` runs daily from EventBridge and can be started manually with `aws stepfunctions start-execution --state-machine-arn <arn> --input '{"source":"MIDAGRI","s3_object":{"bucket":"...","key":"validated.json"}}'`. The external ASL definition is `infrastructure/stepfunctions/ingestion.asl.json`.

States are FetchAgriculturalPrices, ValidateDataset, StoreRawDataset, NormalizeAgriculturalPrices, PersistNormalizedPrices, CalculatePriceTrends, PublishDataset, and HandleFailure. Each invokes the ingestion Lambda with a small reference payload. Raw data belongs in S3; normalized data belongs in DynamoDB. Dataset IDs and hashes provide idempotency, while publication happens only after the previous states succeed.

Transient Lambda/network/throttling errors retry up to three times with exponential backoff. Validation errors go to HandleFailure without retry. Failures preserve the last published dataset and include an error reference in the execution history. Review failures in Step Functions Console, CloudWatch Logs, and the ingestion metrics.

