#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$DIR")"
REPO_ROOT="$(dirname "$ROOT")"
CONFIG_LIB="$ROOT/scripts/lib_config.sh"
REPORT_HELPER="$ROOT/scripts/runtime_governance_report.py"

# shellcheck source=tooling/scripts/lib_config.sh
. "$CONFIG_LIB"
load_governance_defaults "$REPO_ROOT"

usage() {
  cat <<'EOF'
Usage:
  bash tooling/cleanup/prune_machine_cache.sh --safe [--dry-run]
  bash tooling/cleanup/prune_machine_cache.sh --rebuildable [--dry-run] [--include-venv]
  bash tooling/cleanup/prune_machine_cache.sh --aggressive-host [--dry-run]

Modes:
  --safe            Remove only PYTHONPYCACHEPREFIX content.
  --rebuildable     Remove rebuildable machine-cache targets:
                    pycache, pip, npm, playwright, and xdg/pytest-runtime.
  --include-venv    Add the governed runtime venv to the rebuildable set.
  --aggressive-host Alias for --rebuildable --include-venv.
  --dry-run         Report candidates and sizes without deleting anything.
EOF
}

dry_run=0
mode=""
include_venv=0
report_mode=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      dry_run=1
      ;;
    --safe)
      if [ -n "$mode" ]; then
        echo "❌ prune_machine_cache: choose exactly one mode" >&2
        exit 2
      fi
      mode="safe"
      report_mode="safe"
      ;;
    --rebuildable)
      if [ -n "$mode" ]; then
        echo "❌ prune_machine_cache: choose exactly one mode" >&2
        exit 2
      fi
      mode="rebuildable"
      report_mode="rebuildable"
      ;;
    --aggressive-host)
      if [ -n "$mode" ]; then
        echo "❌ prune_machine_cache: choose exactly one mode" >&2
        exit 2
      fi
      mode="rebuildable"
      include_venv=1
      report_mode="aggressive-host"
      ;;
    --include-venv)
      include_venv=1
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "❌ prune_machine_cache: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [ -z "$mode" ]; then
  echo "❌ prune_machine_cache: choose one mode: --safe, --rebuildable, or --aggressive-host" >&2
  usage >&2
  exit 2
fi

if [ "$include_venv" = "1" ] && [ "$mode" != "rebuildable" ] && [ "$mode" != "aggressive-host" ]; then
  echo "❌ prune_machine_cache: --include-venv is only allowed with --rebuildable" >&2
  exit 2
fi

machine_cache_root="$(governance_machine_cache_root_path "$REPO_ROOT")"
pycache_target="${PYTHONPYCACHEPREFIX:-$machine_cache_root/pycache}"
pip_target="${PIP_CACHE_DIR:-$(resolve_repo_path "$REPO_ROOT" "$GOVERNANCE_PIP_CACHE_DIR")}"
npm_target="${NPM_CONFIG_CACHE:-$(resolve_repo_path "$REPO_ROOT" "$GOVERNANCE_NPM_CACHE_DIR")}"
playwright_target="${PLAYWRIGHT_BROWSERS_PATH:-$(resolve_repo_path "$REPO_ROOT" "$GOVERNANCE_PLAYWRIGHT_CACHE_DIR")}"
xdg_root="${XDG_CACHE_HOME:-$(resolve_repo_path "$REPO_ROOT" "$GOVERNANCE_XDG_CACHE_DIR")}"
venv_target="$(governance_runtime_venv_path "$REPO_ROOT")"

targets=("$pycache_target")
if [ "$mode" = "rebuildable" ] || [ "$mode" = "aggressive-host" ]; then
  targets+=(
    "$pip_target"
    "$npm_target"
    "$playwright_target"
    "$xdg_root/pytest-runtime"
  )
fi
if [ "$include_venv" = "1" ]; then
  targets+=("$venv_target")
fi

python_bin="${PYTHON:-python3}"
report_mode="$mode"
run_id="prune-machine-cache-$(date -u +%Y%m%dT%H%M%SZ)-$$"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
start_ts="$(date +%s)"
entries_json="$(mktemp)"
totals_json="$(mktemp)"
extra_json="$(mktemp)"
cleanup_tmp() {
  rm -f "$entries_json" "$totals_json" "$extra_json"
}
trap cleanup_tmp EXIT

"$python_bin" "$REPORT_HELPER" \
  --repo-root "$REPO_ROOT" \
  --command prune_machine_cache \
  --action-kind prune \
  --bucket machine_cache \
  --target "$report_mode" \
  --dry-run "$dry_run" \
  --run-id "$run_id" \
  --started-at "$started_at" \
  --start-ts "$start_ts" \
  --status start \
  --message "machine cache prune started" \
  --ownership-class repo_primary_shared_host \
  --reclaim-class "$report_mode" >/dev/null

"$python_bin" - "$dry_run" "$report_mode" "${targets[@]}" "$entries_json" "$totals_json" "$extra_json" <<'PY'
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def _size_kib(path: Path) -> int:
    if not path.exists():
        return 0
    return int(subprocess.check_output(["du", "-sk", str(path)], text=True).split()[0])


dry_run = sys.argv[1] == "1"
mode = sys.argv[2]
entries_path = Path(sys.argv[-3])
totals_path = Path(sys.argv[-2])
extra_path = Path(sys.argv[-1])
raw_targets = [Path(raw).expanduser() for raw in sys.argv[3:-3]]

seen: set[Path] = set()
targets: list[Path] = []
for path in raw_targets:
    if path in seen:
        continue
    seen.add(path)
    targets.append(path)

entries: list[dict[str, object]] = []
total_before = 0
reclaimed = 0
for path in targets:
    before = _size_kib(path)
    total_before += before
    target_name = path.name or str(path)
    if "venv/default" in path.as_posix():
        ownership_class = "repo_fallback_host"
        reclaim_class = "aggressive_host_cache"
    elif path.name == "pycache":
        ownership_class = "repo_primary_shared_host"
        reclaim_class = "safe_machine_cache"
    else:
        ownership_class = "repo_primary_shared_host"
        reclaim_class = "rebuildable_machine_cache"
    if not dry_run and path.exists():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    after = _size_kib(path)
    reclaimed_now = 0 if dry_run else max(0, before - after)
    reclaimed += reclaimed_now
    entries.append(
        {
            "path_or_object": str(path),
            "target_name": target_name,
            "size_before_kib": before,
            "size_after_kib": after if not dry_run else before,
            "reclaimed_kib": reclaimed_now,
            "ownership_class": ownership_class,
            "reclaim_class": reclaim_class,
            "protected": False,
            "exists_or_present": path.exists() if not dry_run else before > 0,
            "status": "candidate" if before > 0 else "missing",
        }
    )

entries_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
totals_path.write_text(
    json.dumps(
        {
            "candidate_kib": total_before,
            "reclaimed_kib": reclaimed,
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
extra_path.write_text(
    json.dumps(
        {
            "mode": mode,
            "dry_run": dry_run,
            "target_count": len(entries),
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
action = "would prune" if dry_run else "pruned"
print(f"{action} machine cache targets total_kib={total_before}")
for entry in entries:
    print(
        f"- {entry['path_or_object']} size_before_kib={entry['size_before_kib']} "
        f"reclaim_class={entry['reclaim_class']} status={entry['status']}"
    )
PY
rc=$?

status="success"
message="machine cache prune completed"
if [ "$rc" -ne 0 ]; then
  status="fail"
  message="machine cache prune failed"
fi

"$python_bin" "$REPORT_HELPER" \
  --repo-root "$REPO_ROOT" \
  --command prune_machine_cache \
  --action-kind prune \
  --bucket machine_cache \
  --target "$report_mode" \
  --dry-run "$dry_run" \
  --run-id "$run_id" \
  --started-at "$started_at" \
  --start-ts "$start_ts" \
  --status "$status" \
  --message "$message" \
  --ownership-class repo_primary_shared_host \
  --reclaim-class "$report_mode" \
  --entries-json "$entries_json" \
  --totals-json "$totals_json" \
  --extra-json "$extra_json" >/dev/null || true

exit "$rc"
