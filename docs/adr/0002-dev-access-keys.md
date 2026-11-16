# Development IAM access keys under AWS Projects restrictions

Status: implemented locally; AWS provisioning remains unverified.

AWS Projects rejected creation of the GitHub OIDC provider with an explicit SCP deny. The operator requested an IAM access-key alternative without activating advanced features or changing the local default AWS account.

Dev deployment uses a dedicated IAM user with narrowly scoped artifact and CloudFormation permissions. A separate CloudFormation service role manages runtime resources. The key is created manually and stored in GitHub environment secrets, never in CloudFormation outputs or source. Jobs check account 786638967830, region us-east-2, and the environment-specific execution role before deployment.

The standalone bootstrap does not create an OIDC provider or an access-key resource. All existing SCPs still apply; IAM key creation and the full application deployment must be verified in the target account. A static key does not resolve unrelated denials. No automatic account upgrade is authorized.

Production keeps OIDC and its own protected environment. OIDC remains preferable when available because it avoids a stored long-lived deployment credential. The dev alternative requires key rotation and revocation after the demo. The earlier OIDC decision remains applicable to the retained federation path.
