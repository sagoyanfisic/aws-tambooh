#!/usr/bin/env bash
set -euo pipefail
ENVIRONMENT="${1:-dev}"
sam build
sam deploy --config-env default --parameter-overrides "Environment=${ENVIRONMENT} EnableAI=false AnthropicSecretId=tambooh/${ENVIRONMENT}/anthropic-api-key" --no-confirm-changeset

