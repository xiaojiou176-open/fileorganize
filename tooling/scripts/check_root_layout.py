#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

IGNORED_ROOT_ENTRIES = {".git"}


def _load_contract(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid root allowlist contract: {path}")
    return data


def _allowed_entries(contract: dict) -> tuple[set[str], set[str], set[str]]:
    canonical = set(str(item) for item in contract.get("canonical_tracked_entries", []))
    local_only = set(str(item) for item in contract.get("local_only_entries", []))
    if not canonical and not local_only:
        canonical = set(str(item) for item in contract.get("allowed_root_entries", []))
    return canonical | local_only, canonical, local_only


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate repository root exact-shape against contracts/governance/root_allowlist.yaml")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--contract", default="contracts/governance/root_allowlist.yaml", help="Contract path relative to --root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    contract = _load_contract(root / args.contract)
    allowed, canonical, local_only = _allowed_entries(contract)
    purposes = {str(key): str(value) for key, value in dict(contract.get("entry_purposes", {})).items()}
    required_non_empty = [str(item) for item in contract.get("required_non_empty_dirs", [])]
    forbidden_roots = set(str(item) for item in contract.get("forbidden_runtime_roots", []))
    forbidden_patterns = [str(item) for item in contract.get("forbidden_name_patterns", [])]

    entries = sorted(p.name for p in root.iterdir() if p.name not in IGNORED_ROOT_ENTRIES)
    violations: list[str] = []

    overlap = sorted(canonical & local_only)
    for entry in overlap:
        violations.append(f"root entry declared in both canonical_tracked_entries and local_only_entries: {entry}")

    for entry in entries:
        if entry not in allowed:
            violations.append(f"unexpected root entry: {entry}")
        if entry in forbidden_roots:
            violations.append(f"forbidden runtime root in repo root: {entry}")
        for pattern in forbidden_patterns:
            if fnmatch.fnmatch(entry, pattern):
                violations.append(f"forbidden root name pattern {pattern!r}: {entry}")

    missing_allowed = sorted(item for item in canonical if item not in entries)
    for missing in missing_allowed:
        violations.append(f"missing required root entry: {missing}")

    missing_purposes = sorted(item for item in allowed if item not in purposes)
    for missing in missing_purposes:
        violations.append(f"root entry missing purpose annotation: {missing}")

    for rel in required_non_empty:
        target = root / rel
        if not target.exists() or not target.is_dir():
            violations.append(f"required non-empty directory missing: {rel}")
            continue
        if not any(target.iterdir()):
            violations.append(f"required non-empty directory is empty: {rel}")

    if violations:
        sys.stderr.write("root-layout gate failed\n")
        for item in violations:
            sys.stderr.write(f"- {item}\n")
        return 1

    print("root-layout gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
