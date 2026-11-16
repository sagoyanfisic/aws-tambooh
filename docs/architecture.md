# Architecture

React/Vite is hosted from S3 behind CloudFront. API Gateway HTTP API routes to Python 3.12 Lambda. Deterministic calculation services own costs, quantities, inventory deduction, and simulations. DynamoDB stores normalized price records; S3 stores raw imports. EventBridge starts a Step Functions ingestion workflow. Claude is optional and receives verified facts only.

Dev deployment uses a dedicated IAM user's key pair in GitHub environment secrets and a separate CloudFormation execution role. See [dev deployment diagram](diagrams/dev-deployment.mmd). The OIDC sequence below represents the retained production path; AWS Projects currently blocks creation of its provider in the target account.

```mermaid
flowchart LR
 U[Household] --> CF[CloudFront] --> FE[Private S3 frontend]
 U --> API[API Gateway HTTP API] --> L[Lambda API] --> D[(DynamoDB prices)]
 API --> B[Optional Claude API Lambda]
 L --> SNAP[(S3 published JSON snapshots)]
 E[EventBridge schedule] --> SF[Step Functions] --> I[Ingestion Lambda]
 I --> S[(S3 raw and versioned curated datasets)]
 I --> D
```

```mermaid
sequenceDiagram
 participant E as EventBridge
 participant F as Step Functions
 participant I as Ingestion Lambda
 participant D as DynamoDB
 E->>F: daily start
 F->>I: fetch, validate, normalize
 I->>D: idempotent records
 F-->>E: success or last-good data
```

```mermaid
sequenceDiagram
 participant G as GitHub Actions
 participant O as GitHub OIDC
 participant A as AWS STS
 participant C as CloudFormation
 G->>O: signed identity token
 G->>A: AssumeRoleWithWebIdentity
 A-->>G: temporary credentials
 G->>C: SAM deploy with execution role
```

```mermaid
flowchart LR
 Q[Question + verified facts] --> AI[AI Lambda]
 AI -->|enabled| BR[Anthropic Messages API]
 AI -->|disabled/error| FB[Deterministic fallback]
 BR --> V[Validate response]
 FB --> V
 V --> R[Grounded explanation]
```

