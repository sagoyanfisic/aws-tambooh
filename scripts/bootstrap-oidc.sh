#!/usr/bin/env bash
set -euo pipefail
: "${AWS_ACCOUNT_ID:?Set AWS_ACCOUNT_ID}"; : "${GITHUB_OWNER_ID:?Set immutable GitHub owner ID}"; : "${GITHUB_REPOSITORY_ID:?Set immutable GitHub repository ID}"; : "${GITHUB_ENVIRONMENT_ID:?Set immutable GitHub environment ID}"
echo "Create token.actions.githubusercontent.com with audience sts.amazonaws.com, then create a deployment role using infrastructure/roles/github-oidc-trust.yaml."
echo "Trust subject: repo:${GITHUB_OWNER_ID}/${GITHUB_REPOSITORY_ID}:environment:${GITHUB_ENVIRONMENT_ID}"

