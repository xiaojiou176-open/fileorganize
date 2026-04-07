#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def _load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid collaboration surface policy: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate public collaboration surfaces against the English-first policy")
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default="contracts/governance/collaboration_surface_policy.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy = _load_yaml(root / args.policy)
    targets = policy.get("targets", [])
    regex_entries = policy.get("global_forbidden_regex", [])
    errors: list[str] = []

    if not isinstance(targets, list):
        raise SystemExit("invalid collaboration surface policy: targets must be a list")
    if not isinstance(regex_entries, list):
        raise SystemExit("invalid collaboration surface policy: global_forbidden_regex must be a list")

    compiled_patterns: list[re.Pattern[str]] = []
    for entry in regex_entries:
        raw_pattern = str(entry).strip()
        if not raw_pattern:
            errors.append("global_forbidden_regex contains an empty pattern")
            continue
        compiled_patterns.append(re.compile(raw_pattern))

    checked = 0
    for entry in targets:
        if not isinstance(entry, dict):
            errors.append("collaboration surface target must be an object")
            continue

        rel = str(entry.get("path", "")).strip()
        required = entry.get("required_substrings", [])
        forbidden = entry.get("forbidden_substrings", [])

        if not rel:
            errors.append("collaboration surface target missing path")
            continue
        if not isinstance(required, list):
            errors.append(f"{rel}: required_substrings must be a list")
            continue
        if not isinstance(forbidden, list):
            errors.append(f"{rel}: forbidden_substrings must be a list")
            continue

        path = root / rel
        if not path.exists() or not path.is_file():
            errors.append(f"missing collaboration surface file: {rel}")
            continue

        text = path.read_text(encoding="utf-8")
        if not text.strip():
            errors.append(f"{rel}: file is empty")
            continue

        checked += 1
        for needle in required:
            value = str(needle)
            if value not in text:
                errors.append(f"{rel}: missing required text: {value}")

        for marker in forbidden:
            value = str(marker).strip()
            if not value:
                errors.append(f"{rel}: forbidden_substrings contains an empty value")
                continue
            if value in text:
                errors.append(f"{rel}: forbidden text present: {value}")

        for compiled_pattern in compiled_patterns:
            if compiled_pattern.search(text):
                errors.append(f"{rel}: matched forbidden pattern {compiled_pattern.pattern}")

    if errors:
        print("❌ collaboration-surface: failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print("✅ collaboration-surface: passed")
    print(f"checked_files={checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
