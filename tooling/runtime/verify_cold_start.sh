#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$DIR")"

bash "$DIR/runtime_reset.sh" --confirm-workspace-reset
bash "$ROOT/runtime/bootstrap_env.sh"
python3 "$ROOT/scripts/generate_api_contract.py" --check
python3 "$ROOT/scripts/check_runtime_layout.py" --root "$ROOT/.."
python3 "$ROOT/scripts/check_runtime_budget.py" --root "$ROOT/.."
printf 'verify cold start passed\n'
