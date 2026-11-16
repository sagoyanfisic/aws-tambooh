# Security

Runtime roles are separate from deployment roles. S3 blocks public access and encrypts data; DynamoDB uses on-demand billing, encryption, and point-in-time recovery. API inputs are Pydantic-validated. API Gateway throttling is configured in SAM. Claude is opt-in, bounded to 350 output tokens, low temperature, and never owns arithmetic. Do not put household-identifying data in logs.

Development deployment uses dedicated IAM access keys in GitHub environment secrets, as requested after AWS Projects blocked OIDC provider creation. See [access-key setup](access-keys-deployment.md). Keys are created manually, never as CloudFormation resources or outputs, and must be rotated/revoked. The IAM user can deploy only through the separate CloudFormation execution role. GitHub jobs verify account 786638967830 and region us-east-2 before deployment. These credentials remain subject to account SCPs.

Production retains OIDC. OIDC trust uses the exact observed repository/environment subject. Immutable subjects contain names and IDs separated by `@`; environment context uses its name, not its numeric ID. See bootstrap-access.md for the retained OIDC bootstrap. Its CLI apply requires an explicit profile or target CloudShell mode and verifies account 786638967830 before changing IAM. The local default profile is forbidden. Production claim inspection logs selected public claims only, never the complete JWT.

