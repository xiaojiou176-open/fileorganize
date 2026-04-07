#!/usr/bin/env bash
set -euo pipefail

MIN_DISK_GB="${RUNNER_CAPABILITY_MIN_DISK_GB:-10}"
WORKSPACE="${GITHUB_WORKSPACE:-$(pwd)}"
TEMP_DIR="${RUNNER_TEMP:-${WORKSPACE}/.runtime-cache/tmp}"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "❌ runner_capabilities: missing required command: $cmd" >&2
    exit 1
  fi
}

check_writable_dir() {
  local dir="$1"
  mkdir -p "$dir"
  local probe="${dir}/.runner-capability-$$"
  if ! : > "$probe" 2>/dev/null; then
    echo "❌ runner_capabilities: directory is not writable: $dir" >&2
    exit 1
  fi
  rm -f "$probe"
}

check_disk_budget() {
  local dir="$1"
  local available_kb
  available_kb="$(df -Pk "$dir" | awk 'NR==2 {print $4}')"
  if [ -z "$available_kb" ]; then
    echo "❌ runner_capabilities: unable to read disk budget for $dir" >&2
    exit 1
  fi
  local min_kb=$((MIN_DISK_GB * 1024 * 1024))
  if [ "$available_kb" -lt "$min_kb" ]; then
    echo "❌ runner_capabilities: available disk below threshold for $dir (available_kb=$available_kb required_kb=$min_kb)" >&2
    exit 1
  fi
}

require_cmd docker
require_cmd python3
require_cmd git

if ! docker info >/dev/null 2>&1; then
  echo "❌ runner_capabilities: docker daemon unavailable" >&2
  echo "ℹ️ runner_capabilities: Docker app may be running while the daemon is still unavailable; wait for 'docker info' to pass before retrying npm run ci:local." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "❌ runner_capabilities: docker compose plugin unavailable" >&2
  exit 1
fi

check_writable_dir "$WORKSPACE"
check_writable_dir "$TEMP_DIR"
check_disk_budget "$WORKSPACE"
check_disk_budget "$TEMP_DIR"

echo "✅ runner_capabilities: passed"
echo "workspace=$WORKSPACE"
echo "temp_dir=$TEMP_DIR"
echo "min_disk_gb=$MIN_DISK_GB"
