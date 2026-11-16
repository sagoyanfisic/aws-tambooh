#!/usr/bin/env bash
# Called only after GitHub has explicitly configured this job's credentials.
set -euo pipefail
EXPECTED_ACCOUNT="786638967830"
if [ "${GITHUB_ACTIONS:-}" != true ]; then
  echo "Run this check inside GitHub Actions after configuring credentials; local profiles are not used." >&2
  exit 2
fi
: "${AWS_ACCESS_KEY_ID:?Explicit job credentials are required}"
: "${AWS_SECRET_ACCESS_KEY:?Explicit job credentials are required}"
: "${AWS_CLOUDFORMATION_ROLE_ARN:?Set the execution role from bootstrap outputs}"
case "${DEPLOY_ENV:-}" in
  dev|prod) ;;
  *) echo "STOP: DEPLOY_ENV must be dev or prod." >&2; exit 1 ;;
esac
if [ "${AWS_REGION:-}" != us-east-2 ]; then
  echo "STOP: this deployment targets us-east-2 only." >&2
  exit 1
fi
case "$AWS_CLOUDFORMATION_ROLE_ARN" in
  arn:aws:iam::786638967830:role/tambooh-${DEPLOY_ENV}-*) ;;
  *) echo "STOP: execution role must belong to TamBooh account $EXPECTED_ACCOUNT and environment $DEPLOY_ENV." >&2; exit 1 ;;
esac
ACTUAL_ACCOUNT="$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION")"
if [ "$ACTUAL_ACCOUNT" != "$EXPECTED_ACCOUNT" ]; then
  echo "STOP: credentials belong to a different AWS account; no deployment was attempted." >&2
  exit 1
fi
echo "Deployment target verified: $EXPECTED_ACCOUNT / $AWS_REGION"
