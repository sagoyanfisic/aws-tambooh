#!/usr/bin/env bash
set -euo pipefail
: "${API_URL:?Set API_URL to the deployed API URL}"
curl --fail --silent "${API_URL}/api/v1/health" | python -m json.tool

