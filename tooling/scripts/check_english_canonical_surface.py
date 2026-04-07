#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def _load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid English canonical surface policy: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate English-first canonical public surfaces and maintainer-facing diagnostics.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default="contracts/governance/english_canonical_surface_policy.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy = _load_yaml(root / args.policy)
    targets = policy.get("targets", [])
    errors: list[str] = []

    if not isinstance(targets, list):
        raise SystemExit("invalid English canonical surface policy: targets must be a list")

    checked = 0
    for entry in targets:
        if not isinstance(entry, dict):
            errors.append("target entry must be an object")
            continue

        rel_path = str(entry.get("path", "")).strip()
        required = entry.get("required_substrings", [])
        forbidden_regex = entry.get("forbidden_regex", [])
        allowed_regex = entry.get("allowed_regex", [])
        if not rel_path:
            errors.append("target entry missing path")
            continue
        if not isinstance(required, list):
            errors.append(f"{rel_path}: required_substrings must be a list")
            continue
        if not isinstance(forbidden_regex, list):
            errors.append(f"{rel_path}: forbidden_regex must be a list")
            continue
        if not isinstance(allowed_regex, list):
            errors.append(f"{rel_path}: allowed_regex must be a list")
            continue

        path = root / rel_path
        if not path.exists() or not path.is_file():
            errors.append(f"missing English canonical surface file: {rel_path}")
            continue

        text = path.read_text(encoding="utf-8")
        if not text.strip():
            errors.append(f"{rel_path}: file is empty")
            continue

        checked += 1
        for needle in required:
            value = str(needle)
            if value not in text:
                errors.append(f"{rel_path}: missing required text: {value}")

        sanitized_text = text
        for raw in allowed_regex:
            pattern = str(raw).strip()
            if not pattern:
                errors.append(f"{rel_path}: allowed_regex contains an empty value")
                continue
            sanitized_text = re.sub(pattern, "", sanitized_text)

        for raw in forbidden_regex:
            pattern = str(raw).strip()
            if not pattern:
                errors.append(f"{rel_path}: forbidden_regex contains an empty value")
                continue
            if re.search(pattern, sanitized_text):
                errors.append(f"{rel_path}: matched forbidden pattern {pattern}")

    if errors:
        print("❌ english-canonical-surface: failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print("✅ english-canonical-surface: passed")
    print(f"checked_files={checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
