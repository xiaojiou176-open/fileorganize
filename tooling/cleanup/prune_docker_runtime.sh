#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$DIR")"
REPO_ROOT="$(dirname "$ROOT")"
REPORT_HELPER="$ROOT/scripts/runtime_governance_report.py"

usage() {
  cat <<'EOF'
Usage:
  bash tooling/cleanup/prune_docker_runtime.sh --dry-run
  bash tooling/cleanup/prune_docker_runtime.sh --rebuildable [--dry-run]
  bash tooling/cleanup/prune_docker_runtime.sh --aggressive [--dry-run] [--include-image] [--include-volumes]

Modes:
  --dry-run         Audit docker runtime and report reclaim candidates without deleting anything.
  --rebuildable     Prune repo-specific docker build cache only.
  --aggressive      Expand build-cache pruning to repo-related shared layers.
  --include-image   Only valid with --aggressive; unlock canonical image pruning.
  --include-volumes Only valid with --aggressive; unlock protected/optional volume pruning.
EOF
}

dry_run=0
mode=""
report_mode=""
include_image=0
include_volumes=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      dry_run=1
      ;;
    --rebuildable)
      if [ -n "$mode" ]; then
        echo "❌ prune_docker_runtime: choose exactly one mode" >&2
        exit 2
      fi
      mode="rebuildable"
      ;;
    --aggressive)
      if [ -n "$mode" ]; then
        echo "❌ prune_docker_runtime: choose exactly one mode" >&2
        exit 2
      fi
      mode="aggressive"
      ;;
    --include-image)
      include_image=1
      ;;
    --include-volumes)
      include_volumes=1
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "❌ prune_docker_runtime: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [ -z "$mode" ]; then
  if [ "$dry_run" = "1" ]; then
    report_mode="dry-run"
    mode="aggressive"
  else
    echo "❌ prune_docker_runtime: choose one mode: --rebuildable or --aggressive" >&2
    usage >&2
    exit 2
  fi
fi

if [ -z "$report_mode" ]; then
  report_mode="$mode"
fi

if { [ "$include_image" = "1" ] || [ "$include_volumes" = "1" ]; } && [ "$mode" != "aggressive" ]; then
  echo "❌ prune_docker_runtime: --include-image/--include-volumes require --aggressive" >&2
  exit 2
fi

python_bin="${PYTHON:-python3}"
contract_path="$REPO_ROOT/contracts/runtime/filesystem_layout.yaml"
run_id="prune-docker-runtime-$(date -u +%Y%m%dT%H%M%SZ)-$$"
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
  --command prune_docker_runtime \
  --action-kind prune \
  --bucket docker_runtime \
  --target "$report_mode" \
  --dry-run "$dry_run" \
  --run-id "$run_id" \
  --started-at "$started_at" \
  --start-ts "$start_ts" \
  --status start \
  --message "docker runtime prune started" \
  --ownership-class repo_related_shared \
  --reclaim-class "$report_mode" >/dev/null

"$python_bin" - "$REPO_ROOT" "$contract_path" "$mode" "$include_image" "$include_volumes" "$dry_run" "$entries_json" "$totals_json" "$extra_json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

repo_root = Path(sys.argv[1]).resolve()
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from tooling.scripts.docker_runtime_inventory import prune_docker_runtime

contract_path = Path(sys.argv[2]).resolve()
mode = sys.argv[3]
include_image = sys.argv[4] == "1"
include_volumes = sys.argv[5] == "1"
dry_run = sys.argv[6] == "1"
entries_path = Path(sys.argv[7])
totals_path = Path(sys.argv[8])
extra_path = Path(sys.argv[9])

result = prune_docker_runtime(
    repo_root=repo_root,
    contract_path=contract_path,
    mode=mode,
    include_image=include_image,
    include_volumes=include_volumes,
    dry_run=dry_run,
)
entries = list(result.get("entries", []))
totals = dict(result.get("totals", {}))
inventory = dict(result.get("inventory", {}))

entries_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
totals_path.write_text(json.dumps(totals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
extra_path.write_text(
    json.dumps(
        {
            "mode": mode,
            "dry_run": dry_run,
            "include_image": include_image,
            "include_volumes": include_volumes,
            "inventory_status": result.get("status"),
            "inventory": inventory,
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

if result.get("status") == "unavailable":
    print("docker runtime unavailable; no docker prune actions executed")
    raise SystemExit(0)

action = "would prune" if dry_run else "pruned"
print(
    f"{action} docker runtime candidates total_kib={int(totals.get('candidate_kib', 0))} "
    f"reclaimed_kib={int(totals.get('reclaimed_kib', 0))}"
)
for entry in entries:
    print(
        f"- {entry['path_or_object']} size_before_kib={entry['size_before_kib']} "
        f"reclaim_class={entry['reclaim_class']} protected={entry['protected']}"
    )
PY
rc=$?

status="success"
message="docker runtime prune completed"
if [ "$rc" -ne 0 ]; then
  status="fail"
  message="docker runtime prune failed"
fi

"$python_bin" "$REPORT_HELPER" \
  --repo-root "$REPO_ROOT" \
  --command prune_docker_runtime \
  --action-kind prune \
  --bucket docker_runtime \
  --target "$report_mode" \
  --dry-run "$dry_run" \
  --run-id "$run_id" \
  --started-at "$started_at" \
  --start-ts "$start_ts" \
  --status "$status" \
  --message "$message" \
  --ownership-class repo_related_shared \
  --reclaim-class "$report_mode" \
  --entries-json "$entries_json" \
  --totals-json "$totals_json" \
  --extra-json "$extra_json" >/dev/null || true

exit "$rc"
