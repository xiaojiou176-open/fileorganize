#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

import yaml  # type: ignore[import-untyped]

_TOOLING_PYCACHE_ROOTS = (
    Path(__file__).resolve().parent / "__pycache__",
    Path(__file__).resolve().parents[1] / "__pycache__",
)


def _dir_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total / (1024 * 1024)


def _collect_repo_residue(root: Path, patterns: list[str]) -> list[Path]:
    matches: list[Path] = []
    for pattern in patterns:
        try:
            candidates = list(root.glob(pattern))
        except FileNotFoundError:
            continue
        for path in candidates:
            if not path.exists():
                continue
            rel = path.relative_to(root).as_posix()
            if path.is_dir() and rel.startswith("apps/") and rel.endswith("/node_modules"):
                try:
                    next(path.iterdir())
                except StopIteration:
                    continue
                except FileNotFoundError:
                    continue
            if rel.startswith(".runtime-cache/") or rel.startswith(".git/") or rel.startswith(".agents/"):
                continue
            if any(existing in path.parents for existing in matches):
                continue
            matches = [existing for existing in matches if existing not in path.parents]
            matches.append(path)
    return matches


def _glob_paths_size_mb(root: Path, patterns: list[str]) -> float:
    total = 0.0
    for path in _collect_repo_residue(root, patterns):
        if path.is_dir():
            total += _dir_size_mb(path)
        elif path.is_file():
            total += path.stat().st_size / (1024 * 1024)
    return total


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid yaml: {path}")
    return data


def _cleanup_tooling_pycache() -> None:
    for path in _TOOLING_PYCACHE_ROOTS:
        shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate repo runtime cache budget and stale residue policy")
    parser.add_argument("--root", default=".")
    parser.add_argument("--contract", default="contracts/runtime/filesystem_layout.yaml")
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    _cleanup_tooling_pycache()
    contract = _load_yaml(repo_root / args.contract)
    runtime_root = repo_root / ".runtime-cache"
    warn_mb = float(contract.get("budgets_mb", {}).get("repo_runtime_warn", 256))
    error_mb = float(contract.get("budgets_mb", {}).get("repo_runtime_error", 512))
    retention = dict(contract.get("retention", {}))
    residue_globs = [str(item) for item in contract.get("repo_runtime", {}).get("forbidden_repo_residue_globs", [])]
    size_mb = _dir_size_mb(runtime_root)
    residue_mb = _glob_paths_size_mb(repo_root, residue_globs)
    now = time.time()
    stale_hours = float(retention.get("repo_tmp_hours", 24))
    stale_days = float(retention.get("repo_logs_days", 7))

    issues: list[str] = []
    tmp_root = runtime_root / "tmp"
    log_root = runtime_root / "logs"
    if tmp_root.exists():
        for item in tmp_root.iterdir():
            if now - item.stat().st_mtime > stale_hours * 3600:
                issues.append(f"stale tmp runtime residue: {item.relative_to(repo_root).as_posix()}")
    if log_root.exists():
        for item in log_root.rglob("*"):
            if item.is_file() and now - item.stat().st_mtime > stale_days * 86400:
                issues.append(f"stale log runtime residue: {item.relative_to(repo_root).as_posix()}")

    print(f"runtime-budget size_mb={size_mb:.1f} residue_mb={residue_mb:.1f} warn_mb={warn_mb:.1f} error_mb={error_mb:.1f}")
    if residue_mb > 0:
        issues.append(f"illegal repo residue footprint detected: {residue_mb:.1f}MB")
    if size_mb >= error_mb:
        issues.append("error threshold exceeded")
    elif size_mb >= warn_mb:
        issues.append("warn threshold exceeded")

    if issues:
        print("runtime-budget gate failed", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
