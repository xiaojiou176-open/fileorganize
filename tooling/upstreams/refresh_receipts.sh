#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$DIR")"
REPO_ROOT="$(dirname "$ROOT")"
CONFIG_LIB="$ROOT/scripts/lib_config.sh"

# shellcheck source=tooling/scripts/lib_config.sh
. "$CONFIG_LIB"
load_governance_defaults "$REPO_ROOT"
apply_runtime_env_defaults "$REPO_ROOT"

VENV="$(governance_runtime_venv_path "$REPO_ROOT")"
if [ ! -x "$VENV/bin/python" ]; then
  bash "$ROOT/runtime/bootstrap_env.sh"
fi

if [ "$#" -eq 0 ]; then
  set -- --artifacts-root ".runtime-cache" --output-bundle ".runtime-cache/ci/evidence-bundle.json"
fi

exec "$VENV/bin/python" "$ROOT/scripts/refresh_upstream_receipts.py" --root "$REPO_ROOT" "$@"
