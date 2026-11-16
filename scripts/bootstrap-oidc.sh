#!/usr/bin/env bash
set -euo pipefail
# Delegate to the guarded bootstrap. With no --apply it renders a plan only.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec python3 "${SCRIPT_DIR}/bootstrap_access.py" "$@"
