#!/usr/bin/env python3
from __future__ import annotations

import argparse
import atexit
import shutil
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

SKIP_PREFIXES = (".git/", ".runtime-cache/", ".agents/")
PUBLIC_CLEANUP_CMD = "bash tooling/cleanup/prune_repo_runtime.sh"
_TOOLING_PYCACHE_ROOTS = (
    Path(__file__).resolve().parent / "__pycache__",
    Path(__file__).resolve().parents[1] / "__pycache__",
)


def _cleanup_tooling_pycache() -> None:
    for path in _TOOLING_PYCACHE_ROOTS:
        shutil.rmtree(path, ignore_errors=True)


atexit.register(_cleanup_tooling_pycache)


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid yaml: {path}")
    return data


def _size_mb(path: Path) -> float:
    if path.is_file():
        try:
            return path.stat().st_size / (1024 * 1024)
        except FileNotFoundError:
            return 0.0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except FileNotFoundError:
                continue
    return total / (1024 * 1024)


def _safe_glob(root: Path, pattern: str) -> list[Path]:
    try:
        return sorted(root.glob(pattern))
    except FileNotFoundError:
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail when repo-local runtime residue exists outside the governed runtime/cache roots")
    parser.add_argument("--root", default=".")
    parser.add_argument("--contract", default="contracts/runtime/filesystem_layout.yaml")
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    _cleanup_tooling_pycache()
    contract = _load_yaml(repo_root / args.contract)
    globs = [str(item) for item in contract.get("repo_runtime", {}).get("forbidden_repo_residue_globs", [])]

    issues: list[str] = []
    seen: set[Path] = set()
    total_mb = 0.0
    for pattern in globs:
        for path in _safe_glob(repo_root, pattern):
            try:
                exists = path.exists()
            except FileNotFoundError:
                continue
            if not exists or path in seen:
                continue
            rel = path.relative_to(repo_root).as_posix()
            if path.is_dir() and rel.startswith("apps/") and rel.endswith("/node_modules"):
                try:
                    next(path.iterdir())
                except StopIteration:
                    continue
                except FileNotFoundError:
                    continue
            if rel.startswith(SKIP_PREFIXES):
                continue
            if any(parent in seen for parent in path.parents):
                continue
            seen.add(path)
            size_mb = _size_mb(path)
            total_mb += size_mb
            issues.append(f"{rel} ({size_mb:.1f}MB)")

    if issues:
        sys.stderr.write("repo-runtime-residue gate failed\n")
        sys.stderr.write(f"- illegal repo runtime residue footprint: {total_mb:.1f}MB\n")
        for issue in issues:
            sys.stderr.write(f"- {issue}\n")
        sys.stderr.write(f"fix: move runtime outputs to governed caches or run {PUBLIC_CLEANUP_CMD}\n")
        return 1

    print("repo-runtime-residue gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
