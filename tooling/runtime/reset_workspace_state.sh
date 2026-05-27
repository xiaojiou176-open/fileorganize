#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="${FILEYARD_WORKSPACE_ROOT:-$HOME/.fileyard/workspaces/default}"
rm -rf "$WORKSPACE_ROOT/.fileyard"
mkdir -p "$WORKSPACE_ROOT/.fileyard"
printf 'reset workspace state\n'
