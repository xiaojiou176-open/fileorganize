#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid root change control contract: {path}")
    return data


def _allowlist_entries(contract: dict) -> set[str]:
    canonical = set(str(item) for item in contract.get("canonical_tracked_entries", []))
    local_only = set(str(item) for item in contract.get("local_only_entries", []))
    if not canonical and not local_only:
        canonical = set(str(item) for item in contract.get("allowed_root_entries", []))
    return canonical | local_only


def main() -> int:
    parser = argparse.ArgumentParser(description="Require every root entry to be covered by explicit change-control metadata")
    parser.add_argument("--root", default=".")
    parser.add_argument("--allowlist", default="contracts/governance/root_allowlist.yaml")
    parser.add_argument("--contract", default="contracts/governance/root_change_control.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    allowlist = _load_yaml(root / args.allowlist)
    change_control = _load_yaml(root / args.contract)

    allowed = _allowlist_entries(allowlist)
    entries = change_control.get("entries", {})
    if not isinstance(entries, dict):
        raise SystemExit(f"invalid entries mapping: {args.contract}")

    issues: list[str] = []
    for entry in sorted(allowed):
        meta = entries.get(entry)
        if not isinstance(meta, dict):
            issues.append(f"missing change-control metadata for root entry: {entry}")
            continue
        for key in ("owner", "change_class", "approval_rule"):
            if not str(meta.get(key, "")).strip():
                issues.append(f"{entry} change-control missing {key}")

    for entry in sorted(entries):
        if entry not in allowed:
            issues.append(f"change-control entry not present in root allowlist: {entry}")

    if issues:
        sys.stderr.write("root-change-control gate failed\n")
        for issue in issues:
            sys.stderr.write(f"- {issue}\n")
        return 1

    print("root-change-control gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
