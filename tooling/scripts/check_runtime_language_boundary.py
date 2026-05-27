#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml  # type: ignore[import-untyped]

_CJK_REGEX = r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff]"
_STRICT_CLASSES = {"maintainer-facing", "shell-fallback"}
_MIXED_CLASSES = {"mixed-with-allowed-localized-literals"}
_LOCALIZED_CLASSES = {"product-localized"}


def _load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid runtime language boundary policy: {path}")
    return payload


def _sanitize_text(text: str, allowed_regex: list[str], errors: list[str], rel_path: str) -> str:
    sanitized = text
    for raw in allowed_regex:
        pattern = str(raw).strip()
        if not pattern:
            errors.append(f"{rel_path}: allowed_regex contains an empty value")
            continue
        sanitized = re.sub(pattern, "", sanitized)
    return sanitized


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate runtime language boundaries between maintainer diagnostics and product-localized semantics."
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default="contracts/governance/runtime_language_boundary_policy.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy = _load_yaml(root / args.policy)
    targets = policy.get("targets", [])
    errors: list[str] = []

    if not isinstance(targets, list):
        raise SystemExit("invalid runtime language boundary policy: targets must be a list")

    checked = 0
    for entry in targets:
        if not isinstance(entry, dict):
            errors.append("target entry must be an object")
            continue

        rel_path = str(entry.get("path", "")).strip()
        target_class = str(entry.get("class", "")).strip()
        required = entry.get("required_substrings", [])
        forbidden_regex = entry.get("forbidden_regex", [])
        allowed_regex = entry.get("allowed_regex", [])

        if not rel_path:
            errors.append("target entry missing path")
            continue
        if target_class not in _STRICT_CLASSES | _MIXED_CLASSES | _LOCALIZED_CLASSES:
            errors.append(f"{rel_path}: unsupported class {target_class}")
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
            errors.append(f"missing runtime language boundary file: {rel_path}")
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

        if target_class in _LOCALIZED_CLASSES:
            continue

        sanitized = _sanitize_text(text, [str(item) for item in allowed_regex], errors, rel_path)

        for raw in forbidden_regex:
            pattern = str(raw).strip()
            if not pattern:
                errors.append(f"{rel_path}: forbidden_regex contains an empty value")
                continue
            if re.search(pattern, sanitized):
                errors.append(f"{rel_path}: matched forbidden pattern {pattern}")

        if target_class in _STRICT_CLASSES and re.search(_CJK_REGEX, sanitized):
            errors.append(f"{rel_path}: maintainer/shell surface still contains localized text")

    if errors:
        print("❌ runtime-language-boundary: failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print("✅ runtime-language-boundary: passed")
    print(f"checked_files={checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
