#!/usr/bin/env bash
set -euo pipefail

# Repo-local cleanup lane used by quality_gate and pre-push runtime observability.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$DIR")"
REPO_ROOT="$(dirname "$ROOT")"
TARGET_ROOT="${1:-$PWD}"
CONTRACT_PATH="$REPO_ROOT/contracts/runtime/filesystem_layout.yaml"
REPORT_HELPER="$ROOT/scripts/runtime_governance_report.py"

if [ ! -d "$TARGET_ROOT/.runtime-cache" ]; then
  TARGET_ROOT="$REPO_ROOT"
fi

python_bin="$(command -v python3 || command -v python)"
run_id="prune-repo-runtime-$(date -u +%Y%m%dT%H%M%SZ)-$$"
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
  --repo-root "$TARGET_ROOT" \
  --command prune_repo_runtime \
  --action-kind prune \
  --bucket repo_local \
  --target repo_runtime \
  --dry-run 0 \
  --run-id "$run_id" \
  --started-at "$started_at" \
  --start-ts "$start_ts" \
  --status start \
  --message "repo runtime prune started" \
  --ownership-class repo_exclusive \
  --reclaim-class repo_runtime_cleanup >/dev/null

repo_logs_days="$(awk -F': ' '/^  repo_logs_days:/{print $2; exit}' "$CONTRACT_PATH")"
repo_receipts_keep_latest="$(awk -F': ' '/^  repo_receipts_keep_latest:/{print $2; exit}' "$CONTRACT_PATH")"
repo_receipts_days="$(awk -F': ' '/^  repo_receipts_days:/{print $2; exit}' "$CONTRACT_PATH")"
repo_logs_days="${repo_logs_days:-7}"
repo_receipts_keep_latest="${repo_receipts_keep_latest:-20}"
repo_receipts_days="${repo_receipts_days:-$repo_logs_days}"

"$python_bin" - "$TARGET_ROOT" "$entries_json" "$totals_json" "$extra_json" "$repo_logs_days" "$repo_receipts_keep_latest" "$repo_receipts_days" <<'PY'
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

repo_root = Path(sys.argv[1]).resolve()
entries_path = Path(sys.argv[2])
totals_path = Path(sys.argv[3])
extra_path = Path(sys.argv[4])
repo_logs_days = float(sys.argv[5])
repo_receipts_keep_latest = int(sys.argv[6])
repo_receipts_days = float(sys.argv[7])
now = time.time()
runtime_root = repo_root / ".runtime-cache"
logs_root = runtime_root / "logs"


def _size_kib(path: Path) -> int:
    if not path.exists():
        return 0
    return int(subprocess.check_output(["du", "-sk", str(path)], text=True).split()[0])


def _age_days(path: Path) -> float:
    return max(0.0, (now - path.stat().st_mtime) / 86400.0)


def _iter_direct_children(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(path.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True)


entries: list[dict[str, object]] = []


def _append_entry(path: Path, before: int, after: int, reclaim_class: str, *, ownership_class: str = "repo_exclusive") -> None:
    entries.append(
        {
            "path_or_object": str(path),
            "size_before_kib": before,
            "size_after_kib": after,
            "reclaimed_kib": max(0, before - after),
            "ownership_class": ownership_class,
            "reclaim_class": reclaim_class,
            "protected": False,
            "exists_or_present": path.exists(),
            "status": "candidate" if before > 0 else "missing",
        }
    )


def _remove_path(path: Path, reclaim_class: str, *, ownership_class: str = "repo_exclusive") -> None:
    before = _size_kib(path)
    if path.exists():
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
    after = _size_kib(path)
    _append_entry(path, before, after, reclaim_class, ownership_class=ownership_class)


def _remove_named_dirs(scan_root: Path, names: set[str]) -> None:
    if not scan_root.exists():
        return
    targets: list[Path] = []
    # Walk top-down so bulky residue like node_modules can be pruned immediately
    # without traversing every nested package first.
    for dirpath, dirnames, _filenames in os.walk(scan_root, topdown=True):
        base = Path(dirpath)
        for dirname in dirnames:
            if dirname in names:
                targets.append(base / dirname)
        dirnames[:] = [dirname for dirname in dirnames if dirname not in names]
    for target in targets:
        _remove_path(target, "illegal_repo_residue")


legacy_dirs = [
    runtime_root / "closure-backups",
    runtime_root / "coverage",
    runtime_root / "manual-debug",
    runtime_root / "mutmut",
    runtime_root / "mypy",
    runtime_root / "ruff",
    runtime_root / "release-assets",
    runtime_root / "temp",
    runtime_root / "tmp-ui-audit-tests",
    runtime_root / "tmp-ui-audit-tests-main-block",
    runtime_root / "tmp-ui-audit-tests-main-pass",
    runtime_root / "tmp-ui-audit-tests-main-warning-false",
    runtime_root / "test" / "mutmut",
    runtime_root / "venv",
]
for path in legacy_dirs:
    if path.exists():
        _remove_path(path, "legacy_repo_runtime")

for scan_root in (
    repo_root / "apps",
    repo_root / "packages",
    repo_root / "tests",
    repo_root / "tooling",
    repo_root,
):
    _remove_named_dirs(scan_root, {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})
_remove_named_dirs(repo_root / "apps", {"node_modules", "dist", "dist-ssr"})

for target in ("build", "coverage", "dist", "htmlcov", "logs", "playwright-report"):
    path = repo_root / target
    if path.exists():
        _remove_path(path, "illegal_repo_residue")

for path in repo_root.rglob("*.egg-info"):
    if path.exists():
        _remove_path(path, "illegal_repo_residue")

for path in (
    runtime_root / "build" / "tooling" / "mypy",
    runtime_root / "build" / "tooling" / "ruff",
    runtime_root / "build" / "apps" / "webui",
    runtime_root / "test",
):
    if path.exists():
        _remove_path(path, "safe_repo_cache")

tmp_root = runtime_root / "tmp"
if tmp_root.exists():
    for child in list(tmp_root.iterdir()):
        _remove_path(child, "repo_tmp_cleanup")

for path in list(runtime_root.glob("*")):
    if path.is_file():
        _remove_path(path, "runtime_root_file_cleanup")

protected_files = {
    logs_root / "quality-gate" / "summary.json",
    logs_root / "quality-gate" / "host-summary.json",
    logs_root / "quality-gate" / ".step-summary.jsonl",
    logs_root / "quality-gate" / ".host-step-summary.jsonl",
    logs_root / "runtime-governance" / "summary.json",
    logs_root / "scancode" / "summary.json",
    runtime_root / "ci" / "evidence-bundle.json",
}


def _prune_receipt_runs(runs_root: Path, reclaim_class: str) -> None:
    run_dirs = [path for path in _iter_direct_children(runs_root) if path.is_dir()]
    protected = set(run_dirs[:repo_receipts_keep_latest])
    for path in run_dirs:
        if path in protected:
            continue
        if _age_days(path) <= repo_receipts_days:
            continue
        _remove_path(path, reclaim_class)


for runs_root, reclaim_class in (
    (logs_root / "quality-gate" / "runs", "receipt_retention"),
    (logs_root / "runtime-governance" / "runs", "receipt_retention"),
):
    if runs_root.exists():
        _prune_receipt_runs(runs_root, reclaim_class)

for root, reclaim_class in (
    (logs_root / "scancode", "receipt_lane_retention"),
    (runtime_root / "ci", "receipt_lane_retention"),
):
    if not root.exists():
        continue
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path in protected_files:
            continue
        if _age_days(path) <= repo_logs_days:
            continue
        _remove_path(path, reclaim_class)

for path in runtime_root.rglob("*"):
    if not path.is_file():
        continue
    if path in protected_files:
        continue
    if any(part == "runs" for part in path.parts):
        continue
    if _age_days(path) <= repo_logs_days:
        continue
    _remove_path(path, "repo_log_retention")

entries_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
totals_path.write_text(
    json.dumps(
        {
            "candidate_kib": sum(int(entry["size_before_kib"]) for entry in entries),
            "reclaimed_kib": sum(int(entry["reclaimed_kib"]) for entry in entries),
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
            "repo_logs_days": repo_logs_days,
            "repo_receipts_keep_latest": repo_receipts_keep_latest,
            "repo_receipts_days": repo_receipts_days,
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

print("pruned repo runtime cache")
PY
rc=$?

status="success"
message="repo runtime prune completed"
if [ "$rc" -ne 0 ]; then
  status="fail"
  message="repo runtime prune failed"
fi

"$python_bin" "$REPORT_HELPER" \
  --repo-root "$TARGET_ROOT" \
  --command prune_repo_runtime \
  --action-kind prune \
  --bucket repo_local \
  --target repo_runtime \
  --dry-run 0 \
  --run-id "$run_id" \
  --started-at "$started_at" \
  --start-ts "$start_ts" \
  --status "$status" \
  --message "$message" \
  --ownership-class repo_exclusive \
  --reclaim-class repo_runtime_cleanup \
  --entries-json "$entries_json" \
  --totals-json "$totals_json" \
  --extra-json "$extra_json" >/dev/null || true

exit "$rc"
