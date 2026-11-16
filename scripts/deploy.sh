#!/usr/bin/env bash
set -euo pipefail
ENVIRONMENT="${1:-dev}"
case "$ENVIRONMENT" in
  dev|prod) ;;
  *) echo "Usage: scripts/deploy.sh dev|prod" >&2; exit 2 ;;
esac
DEPLOY_REGION="${AWS_REGION:-us-east-2}"
ARTIFACTS_BUCKET="${AWS_ARTIFACTS_BUCKET:-tambooh-${ENVIRONMENT}-artifacts-786638967830}"
CFN_ROLE_ARN="${AWS_CLOUDFORMATION_ROLE_ARN:-arn:aws:iam::786638967830:role/tambooh-${ENVIRONMENT}-cloudformation}"
sam validate --lint --region "$DEPLOY_REGION" --template-file template.yaml
sam build
sam deploy --stack-name "tambooh-${ENVIRONMENT}" --region "$DEPLOY_REGION" \
  --s3-bucket "$ARTIFACTS_BUCKET" --role-arn "$CFN_ROLE_ARN" \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides "Environment=${ENVIRONMENT} EnableAI=false AnthropicSecretId=tambooh/${ENVIRONMENT}/anthropic-api-key" \
  --no-confirm-changeset --no-fail-on-empty-changeset

