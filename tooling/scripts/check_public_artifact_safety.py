#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def _load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid public artifact policy: {path}")
    return payload


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate repo-side public artifact safety posture")
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default="contracts/governance/public_artifact_policy.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy_path = root / args.policy
    policy = _load_yaml(policy_path)
    contract_rel = str(policy.get("provenance_contract", "contracts/governance/public_asset_provenance.yaml"))
    contract = _load_yaml(root / contract_rel)
    errors: list[str] = []

    entries = contract.get("assets", [])
    if not isinstance(entries, list):
        raise SystemExit("invalid public asset provenance contract: assets must be a list")

    declared: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("public asset provenance entry must be an object")
            continue
        rel = str(entry.get("path", "")).strip()
        if rel:
            declared[rel] = entry

    forbidden_suffixes = {str(item).lower() for item in policy.get("global_forbidden_extensions", [])}
    text_scan = policy.get("text_scan", {})
    text_enabled = isinstance(text_scan, dict) and bool(text_scan.get("enabled", False))
    text_extensions = {str(item).lower() for item in text_scan.get("extensions", [])} if isinstance(text_scan, dict) else set()
    forbidden_patterns = [re.compile(str(item)) for item in text_scan.get("forbidden_regex", [])] if isinstance(text_scan, dict) else []

    documented_paths = set()
    doc_surfaces = policy.get("documentation_surfaces", [])
    if isinstance(doc_surfaces, list):
        for surface in doc_surfaces:
            if not isinstance(surface, dict):
                errors.append("documentation surface must be an object")
                continue
            rel = str(surface.get("path", "")).strip()
            required = surface.get("required_substrings", [])
            if not rel:
                errors.append("documentation surface missing path")
                continue
            documented_paths.add(rel)
            path = root / rel
            if not path.exists():
                errors.append(f"missing documentation surface: {rel}")
                continue
            contents = path.read_text(encoding="utf-8")
            for snippet in required if isinstance(required, list) else []:
                text = str(snippet)
                if text not in contents:
                    errors.append(f"{rel}: missing required snippet: {text}")

    audited_roots = policy.get("audited_roots", [])
    if not isinstance(audited_roots, list):
        raise SystemExit("invalid public artifact policy: audited_roots must be a list")

    declared_under_roots: set[str] = set()
    checked_files = 0

    for root_entry in audited_roots:
        if not isinstance(root_entry, dict):
            errors.append("audited root entry must be an object")
            continue
        rel_root = str(root_entry.get("path", "")).strip()
        if not rel_root:
            errors.append("audited root missing path")
            continue
        target_root = root / rel_root
        if not target_root.exists() or not target_root.is_dir():
            errors.append(f"audited root missing or not a directory: {rel_root}")
            continue

        expected_kinds = {str(item) for item in root_entry.get("expected_kinds", [])}
        expected_statuses = {str(item) for item in root_entry.get("expected_statuses", [])}
        expected_licenses = {str(item) for item in root_entry.get("expected_licenses", [])}
        allowed_extensions = {str(item).lower() for item in root_entry.get("allowed_extensions", [])}

        for file_path in sorted(target_root.rglob("*")):
            if not file_path.is_file():
                continue
            checked_files += 1
            rel_path = str(file_path.relative_to(root))
            declared_under_roots.add(rel_path)
            entry = declared.get(rel_path)
            if entry is None:
                errors.append(f"{rel_path}: file exists under audited root but is not declared in {contract_rel}")
                continue

            suffix = file_path.suffix.lower()
            if suffix in forbidden_suffixes:
                errors.append(f"{rel_path}: forbidden public artifact extension {suffix}")
            if allowed_extensions and suffix not in allowed_extensions:
                errors.append(f"{rel_path}: extension {suffix or '<none>'} is not allowed under {rel_root}")

            kind = str(entry.get("kind", "")).strip()
            status = str(entry.get("status", "")).strip()
            license_name = str(entry.get("license", "")).strip()
            if expected_kinds and kind not in expected_kinds:
                errors.append(f"{rel_path}: kind {kind or '<missing>'} is not allowed under {rel_root}")
            if expected_statuses and status not in expected_statuses:
                errors.append(f"{rel_path}: status {status or '<missing>'} is not allowed under {rel_root}")
            if expected_licenses and license_name not in expected_licenses:
                errors.append(f"{rel_path}: license {license_name or '<missing>'} is not allowed under {rel_root}")

            if text_enabled and suffix in text_extensions:
                contents = _read_text(file_path)
                for pattern in forbidden_patterns:
                    if pattern.search(contents):
                        errors.append(f"{rel_path}: forbidden public artifact content matched /{pattern.pattern}/")

    if bool(policy.get("require_declared_entries_cover_all_files", False)):
        for rel_path in declared:
            if rel_path not in declared_under_roots:
                errors.append(f"{rel_path}: declared public artifact path is outside audited roots")

    if errors:
        print("❌ public-artifact-safety: failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print("✅ public-artifact-safety: passed")
    print(f"checked_files={checked_files}")
    print(f"documentation_surfaces={len(documented_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
