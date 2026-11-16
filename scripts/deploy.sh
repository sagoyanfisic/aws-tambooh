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
PARAMETER_OVERRIDES=("Environment=${ENVIRONMENT}" "EnableAI=false" "AnthropicSecretId=tambooh/${ENVIRONMENT}/anthropic-api-key")
DEPLOY_OPTIONS=(--no-confirm-changeset --no-fail-on-empty-changeset)
case "${SAM_EXECUTE_CHANGESET:-true}" in
  true) ;;
  false) DEPLOY_OPTIONS+=(--no-execute-changeset) ;;
  *) echo "SAM_EXECUTE_CHANGESET must be true or false." >&2; exit 2 ;;
esac
# Omit this override when unset so SAM preserves an imported stack's existing value.
if [ -n "${AWS_RAW_DATA_BUCKET_NAME:-}" ]; then
  case "$AWS_RAW_DATA_BUCKET_NAME" in
    tambooh-${ENVIRONMENT}-rawdatabucket-*) ;;
    *) echo "Raw data bucket must use the tambooh-${ENVIRONMENT}-rawdatabucket- prefix." >&2; exit 2 ;;
  esac
  PARAMETER_OVERRIDES+=("RawDataBucketName=${AWS_RAW_DATA_BUCKET_NAME}")
fi
sam validate --lint --region "$DEPLOY_REGION" --template-file template.yaml
sam build
sam deploy --stack-name "tambooh-${ENVIRONMENT}" --region "$DEPLOY_REGION" \
  --s3-bucket "$ARTIFACTS_BUCKET" --role-arn "$CFN_ROLE_ARN" \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides "${PARAMETER_OVERRIDES[@]}" \
  "${DEPLOY_OPTIONS[@]}"
if [ "${SAM_EXECUTE_CHANGESET:-true}" = false ]; then
  echo "Change set prepared for review only; application resource changes were not executed."
fi

