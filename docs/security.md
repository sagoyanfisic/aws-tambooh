# Security

Runtime roles are separate from deployment roles. S3 blocks public access and encrypts data; DynamoDB uses on-demand billing, encryption, and point-in-time recovery. API inputs are Pydantic-validated. API Gateway throttling is configured in SAM. Claude is opt-in, bounded to 350 output tokens, low temperature, and never owns arithmetic. Do not put household-identifying data in logs.

GitHub OIDC must be bootstrapped with exact immutable owner/repository/environment identifiers. Because this local workspace is not connected to GitHub, final claim values cannot be determined here; the bootstrap script requires them explicitly and the trust policy fails closed with placeholders.

