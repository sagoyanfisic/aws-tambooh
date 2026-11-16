# Deployment

Target account: `786638967830`. Default region: `us-east-2` (Ohio).
The configured development stack is `tambooh-dev`.

**Current dev authentication:** use [the access-key deployment guide](access-keys-deployment.md). The AWS Projects account rejected OIDC provider creation with an SCP deny, so dev now reads `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from GitHub **environment secrets**. Create permissions with `infrastructure/bootstrap/console-access-keys.json` and replace `AWS_CLOUDFORMATION_ROLE_ARN` with its output. The OIDC setup described below applies to production or accounts that permit it; it is not a prerequisite for the current dev key workflow. No AWS changes have been made by preparing this configuration.

## One-time AWS setup

Create this artifact bucket in **us-east-2**:

```text
tambooh-dev-artifacts-786638967830
```

Keep all S3 Block Public Access options enabled, use SSE-S3 encryption, and enable versioning. This is the deployment artifact bucket; SAM creates the application's raw-data and frontend buckets separately.

If using AWS CLI from an authenticated terminal or CloudShell, create the bucket with:

```bash
aws s3api create-bucket \
  --bucket tambooh-dev-artifacts-786638967830 \
  --region us-east-2 \
  --create-bucket-configuration LocationConstraint=us-east-2
aws s3api put-public-access-block \
  --bucket tambooh-dev-artifacts-786638967830 \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption \
  --bucket tambooh-dev-artifacts-786638967830 \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-bucket-versioning \
  --bucket tambooh-dev-artifacts-786638967830 \
  --versioning-configuration Status=Enabled
```

This name is proposed, not confirmed available. If another account owns it, select a unique alternative and update `samconfig.toml` and `AWS_ARTIFACTS_BUCKET`.

For development, create the dedicated deployment user and CloudFormation execution role using [the access-key bootstrap](access-keys-deployment.md). This creates permissions only; generate the user key manually after the stack succeeds. The Anthropic key is separate and is not needed for ingestion.

## GitHub environment

In **sagoyanfisic/aws-tambooh → Settings → Environments → dev**, configure:

| Kind | Name | Value |
|---|---|---|
| Secret | AWS_ACCESS_KEY_ID | Dedicated deployment user's key ID |
| Secret | AWS_SECRET_ACCESS_KEY | Matching secret access key |
| Variable | AWS_REGION | us-east-2 |
| Variable | AWS_ARTIFACTS_BUCKET | tambooh-dev-artifacts-786638967830 |
| Variable | AWS_CLOUDFORMATION_ROLE_ARN | CloudFormationExecutionRoleArn output from the key-access stack |

With the default bootstrap prefix, the execution role is `arn:aws:iam::786638967830:role/tambooh-dev-keys-cloudformation`. Replace the previous variable value; the failed OIDC bootstrap's role must not be assumed to exist. `AWS_DEPLOY_ROLE_ARN` is no longer used for dev.

Production retains OIDC and requires an exact verified subject, an allowed provider, an independently configured execution/deployment role and artifact bucket, and branch/approval restrictions in environment `production`. See [OIDC bootstrap](bootstrap-access.md) for the retained federation procedure; the supplied bootstrap is dev-specific and must not be reused as a production trust. Production has no fallback to development credentials.

Deployments are manual: all deployment workflows use `workflow_dispatch`; pushing code does not deploy. Keep `master` as the default branch and use `dev` as the development branch. First merge the workflow definitions into `master`, since GitHub requires a manually triggered workflow to exist on the default branch before it appears as runnable in Actions.

To deploy development, open **Actions → Deploy dev → Run workflow**, choose branch **dev**, then confirm **Run workflow**. Alternatively, select **Deploy TamBooh**, choose branch **dev** and input environment **dev**. Both call `scripts/deploy.sh` to validate, build and deploy into us-east-2. The selected branch must contain these updated workflow and application files.

In **Settings → Environments → dev → Deployment branches and tags**, authorize the exact `dev` branch. The environment named `dev` stores deployment variables and access rules; the Git branch named `dev` stores code. They are separate settings.

Production uses GitHub environment `production`, a separate `tambooh-prod` stack, deployment/execution roles and artifact bucket. Configure approval and branch restrictions before using it. No production resources are created by preparing these files.

## Local deployment

Install Python 3.12, SAM CLI, AWS CLI, make and rsync. Use an explicitly named target-account AWS SSO/profile session; never the local default profile.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
# This named profile must already be authorized for account 786638967830.
AWS_PROFILE=tambooh-new aws sts get-caller-identity --region us-east-2
# Inspect Account above before continuing. Export the execution-role output.
export AWS_CLOUDFORMATION_ROLE_ARN=arn:aws:iam::786638967830:role/tambooh-dev-keys-cloudformation
AWS_PROFILE=tambooh-new bash scripts/deploy.sh dev
```

`samconfig.toml` contains public configuration only. The script supplies stack, region, bucket, execution role and parameters explicitly. To use a different bucket/role, export `AWS_ARTIFACTS_BUCKET` and `AWS_CLOUDFORMATION_ROLE_ARN`. The runtime model stays arm64 Python 3.12.

## Optional Claude

First deploy with `EnableAI=false`; no Anthropic secret is required for ingestion. To enable AI later, create `tambooh/dev/anthropic-api-key` in Secrets Manager in **us-east-2**, containing a JSON object with key `ANTHROPIC_API_KEY`. Update `EnableAI` only after confirming model/account access. Never put its value into SAM parameters, frontend variables or GitHub Actions. Rotate through Secrets Manager; cached values refresh in new Lambda environments.

## After deployment

Inspect CloudFormation outputs for `IngestionStateMachineArn`, `RawBucketName` and `ApiUrl`. Start the first ingestion manually using `events/ingestion.json` and inspect every source result. Successful infrastructure deployment does not prove that MIDAGRI is reachable or that its live PDF layouts are supported.

The Lambda workflow deploys the stack but does not upload frontend assets. Build the React app and upload its build separately to `FrontendBucketName`, served through `FrontendDistributionDomain`.

Production data mode is DynamoDB. `TAMBOOH_DATA_MODE=demo` is only for local demonstrations; demo fixtures are not included in the Lambda build artifacts.
