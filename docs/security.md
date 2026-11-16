# Security

Runtime roles are separate from deployment roles. S3 blocks public access and encrypts data; DynamoDB uses on-demand billing, encryption, and point-in-time recovery. API inputs are Pydantic-validated. API Gateway throttling is configured in SAM. Claude is opt-in, bounded to 350 output tokens, low temperature, and never owns arithmetic. Do not put household-identifying data in logs.

GitHub OIDC trust uses the exact subject emitted by the development job. Immutable subjects contain names and IDs separated by `@`; environment context uses its name, not its numeric ID. See bootstrap-access.md. Apply requires an explicit profile or target CloudShell mode and verifies account 786638967830 before changing IAM. The local default profile is forbidden. The workflow logs selected public claims only, never the complete JWT.

