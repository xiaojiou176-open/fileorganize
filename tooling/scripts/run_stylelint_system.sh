#!/usr/bin/env bash
set -euo pipefail

# Keep pre-commit / pre-push / quality_gate stylelint execution independent
# from repo-local node_modules so CI and local gate paths share one contract.
BIN="$(
  npx --yes \
    -p stylelint@16.23.0 \
    -p stylelint-config-standard@39.0.1 \
    -p stylelint-config-recommended-scss@15.0.1 \
    -p @stylistic/stylelint-plugin@3.1.3 \
    -c 'command -v stylelint'
)"
CONFIG_BASEDIR="$(cd "$(dirname "$BIN")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

"$BIN" --config-basedir "$CONFIG_BASEDIR" --config "$REPO_ROOT/tooling/config/stylelintrc.json" --fix "$@"
