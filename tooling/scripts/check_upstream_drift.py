#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

# quality_gate/local_quality_gate/pre-push use this script to prove upstream drift stays governed.
FLOATING_PATTERNS = (
    re.compile(r":latest\b", re.IGNORECASE),
    re.compile(r"\b@latest\b", re.IGNORECASE),
    re.compile(r"\bmain\b", re.IGNORECASE),
)


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid yaml: {path}")
    return data


def _split_source(source: str) -> list[str]:
    return [part.strip() for part in source.split("+") if part.strip()]


def _source_exists(root: Path, source: str) -> bool:
    candidate = source.split()[0]
    if candidate.isupper() and "_" in candidate:
        return True
    return (root / candidate).exists()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate upstream inventory, checksum, and compat drift")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    inventory = _load_yaml(root / "contracts/upstreams/upstream_inventory.yaml")
    matrix = _load_yaml(root / "contracts/upstreams/compatibility_matrix.yaml")
    license_policy = _load_yaml(root / "contracts/upstreams/license_policy.yaml")
    registry = _load_yaml(root / "contracts/upstreams/upstream_registry.yaml")
    required_fields = set(str(item) for item in registry.get("required_inventory_fields", []))
    class_required_fields = {
        str(class_name): {str(field) for field in fields if str(field).strip()}
        for class_name, fields in registry.get("class_required_fields", {}).items()
        if isinstance(fields, list)
    }
    matrix_ids = {str(item.get("upstream_id", "")) for item in matrix.get("matrix", []) if isinstance(item, dict)}
    license_buckets = set(license_policy.get("policies", {}).get("allow_review_buckets", []))
    license_buckets.update(license_policy.get("policies", {}).get("deny_licenses", []))
    allowed_failures = {
        "repo_logic",
        "repo_config",
        "workspace_input",
        "cache_state",
        "ci_environment",
        "upstream_python",
        "upstream_node",
        "upstream_image",
        "upstream_browser",
        "upstream_model",
    }

    issues: list[str] = []
    seen_ids: set[str] = set()
    for item in inventory.get("upstreams", []):
        if not isinstance(item, dict):
            issues.append("inventory contains non-object upstream entry")
            continue
        missing = sorted(required_fields - set(item))
        if missing:
            issues.append(f"{item.get('id', '<unknown>')} missing fields: {', '.join(missing)}")
        class_name = str(item.get("class", "")).strip()
        class_missing = sorted(field for field in class_required_fields.get(class_name, set()) if field not in item)
        if class_missing:
            issues.append(f"{item.get('id', '<unknown>')} missing {class_name} fields: {', '.join(class_missing)}")
        upstream_id = str(item.get("id", "")).strip()
        if not upstream_id:
            issues.append("inventory entry missing id")
            continue
        if upstream_id in seen_ids:
            issues.append(f"duplicate upstream id: {upstream_id}")
        seen_ids.add(upstream_id)
        if item.get("floating_allowed") is not False:
            issues.append(f"{upstream_id} must set floating_allowed=false")
        if str(item.get("failure_domain", "")) not in allowed_failures:
            issues.append(f"{upstream_id} uses unknown failure_domain: {item.get('failure_domain')}")
        license_name = str(item.get("license", ""))
        if license_name and license_name not in license_buckets:
            issues.append(f"{upstream_id} references unknown license bucket: {license_name}")
        pinned_value = str(item.get("pinned_value", ""))
        for pattern in FLOATING_PATTERNS:
            if pattern.search(pinned_value):
                issues.append(f"{upstream_id} uses floating pinned_value: {pinned_value}")
                break
        checksum = str(item.get("checksum_or_digest", "")).strip()
        if not checksum:
            issues.append(f"{upstream_id} missing checksum_or_digest")
        if not str(item.get("source_url", "")).strip():
            issues.append(f"{upstream_id} missing source_url")
        for source in _split_source(str(item.get("source", ""))):
            if not _source_exists(root, source):
                issues.append(f"{upstream_id} source path missing: {source}")
        if upstream_id not in matrix_ids:
            issues.append(f"{upstream_id} missing from compatibility matrix")

    if issues:
        sys.stderr.write("upstream-drift gate failed\n")
        for issue in issues:
            sys.stderr.write(f"- {issue}\n")
        return 1

    print(json.dumps({"status": "pass", "checked": len(inventory.get("upstreams", []))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
