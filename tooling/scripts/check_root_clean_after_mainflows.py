#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

IGNORED_ROOT_ENTRIES = {".git"}
KNOWN_FORBIDDEN = {
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "build",
    "coverage",
    "dist",
    "htmlcov",
    "logs",
    "playwright-report",
}


def _load_contract(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid yaml: {path}")
    return data


def _allowed_entries(contract: dict) -> set[str]:
    canonical = set(str(item) for item in contract.get("canonical_tracked_entries", []))
    local_only = set(str(item) for item in contract.get("local_only_entries", []))
    if not canonical and not local_only:
        return set(str(item) for item in contract.get("allowed_root_entries", []))
    return canonical | local_only


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect root pollution after main flows")
    parser.add_argument("--root", default=".")
    parser.add_argument("--contract", default="contracts/governance/root_allowlist.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    contract = _load_contract(root / args.contract)
    allowed = _allowed_entries(contract)
    forbidden_patterns = [str(item) for item in contract.get("forbidden_name_patterns", [])]
    forbidden_runtime_roots = set(str(item) for item in contract.get("forbidden_runtime_roots", [])) | KNOWN_FORBIDDEN

    issues: list[str] = []
    for entry in sorted(p.name for p in root.iterdir() if p.name not in IGNORED_ROOT_ENTRIES):
        if entry not in allowed:
            issues.append(f"unexpected root residue: {entry}")
        if entry in forbidden_runtime_roots:
            issues.append(f"forbidden runtime root present: {entry}")
        for pattern in forbidden_patterns:
            if fnmatch.fnmatch(entry, pattern):
                issues.append(f"forbidden runtime residue pattern {pattern}: {entry}")

    if issues:
        sys.stderr.write("root-clean-after-mainflows gate failed\n")
        for issue in issues:
            sys.stderr.write(f"- {issue}\n")
        return 1

    print("root-clean-after-mainflows gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
