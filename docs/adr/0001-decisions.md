# Architecture decisions

## SAM
SAM keeps Lambda, API, Step Functions, and IAM definitions close to the application and reproducible in CI.

## DynamoDB
Normalized records use a composite key (`pk`, `sk`) and on-demand capacity to match sparse, variable workloads.

## OIDC
GitHub federation avoids long-lived keys; exact immutable repository claims are required.
The requested dev exception for AWS Projects is recorded in [ADR 0002](0002-dev-access-keys.md).

## Claude API
Claude is an optional explanation layer, not a source of facts or arithmetic. The backend retrieves its key from Secrets Manager in AWS and never exposes it to the browser.

## Deterministic recommendations
Costs, quantities, budgets, inventory deduction, and scenarios run in Python so outputs remain reproducible and testable.

## Official datasets
Import adapters preserve source metadata and refuse to imply live data when only a validated export is available.

