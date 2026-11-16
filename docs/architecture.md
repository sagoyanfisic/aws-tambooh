# Architecture

React/Vite is hosted from S3 behind CloudFront. API Gateway HTTP API routes to Python 3.12 Lambda. Deterministic calculation services own costs, quantities, inventory deduction, and simulations. DynamoDB stores normalized price records; S3 stores raw imports. EventBridge starts a Step Functions ingestion workflow. Claude is optional and receives verified facts only.

```mermaid
flowchart LR
 U[Household] --> CF[CloudFront] --> FE[Private S3 frontend]
 U --> API[API Gateway HTTP API] --> L[Lambda API] --> D[(DynamoDB prices)]
 L --> B[Optional Claude API Lambda]
 E[EventBridge schedule] --> SF[Step Functions] --> I[Ingestion Lambda]
 I --> S[(S3 raw datasets)]
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
 G->>O: signed identity token
 G->>A: AssumeRoleWithWebIdentity
 A-->>G: temporary credentials
 G->>A: SAM deploy
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

