#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid yaml: {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate upstream compatibility matrix coverage")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    inventory = _load_yaml(root / "contracts/upstreams/upstream_inventory.yaml")
    matrix = _load_yaml(root / "contracts/upstreams/compatibility_matrix.yaml")
    host_capability_policy = _load_yaml(root / "contracts/upstreams/host_capability_policy.yaml")
    matrix_items = [item for item in matrix.get("matrix", []) if isinstance(item, dict)]
    matrix_ids = {str(item.get("upstream_id", "")) for item in matrix_items}
    issues: list[str] = []
    pair_required_by_mode = {
        str(mode): {str(field) for field in payload.get("required_pair_fields", []) if str(field).strip()}
        for mode, payload in host_capability_policy.get("modes", {}).items()
        if isinstance(payload, dict)
    }
    for item in inventory.get("upstreams", []):
        if not isinstance(item, dict):
            continue
        upstream_id = str(item.get("id", "")).strip()
        if upstream_id and upstream_id not in matrix_ids:
            issues.append(f"missing compatibility coverage for {upstream_id}")

    required_pair_fields = {
        "verification_suite",
        "verification_mode",
        "verification_artifact",
        "verification_max_age_hours",
        "rollback_baseline",
    }
    for item in matrix_items:
        upstream_id = str(item.get("upstream_id", "")).strip() or "<unknown>"
        pairs = item.get("supported_pairs", [])
        if not isinstance(pairs, list) or not pairs:
            issues.append(f"{upstream_id} must define at least one supported_pair")
            continue
        for idx, pair in enumerate(pairs, 1):
            if not isinstance(pair, dict):
                issues.append(f"{upstream_id} supported_pair[{idx}] must be an object")
                continue
            missing = sorted(field for field in required_pair_fields if not str(pair.get(field, "")).strip())
            if missing:
                issues.append(f"{upstream_id} supported_pair[{idx}] missing fields: {', '.join(missing)}")
            verification_mode = str(pair.get("verification_mode", "")).strip()
            extra_required = sorted(
                field for field in pair_required_by_mode.get(verification_mode, set()) if not str(pair.get(field, "")).strip()
            )
            if extra_required:
                issues.append(
                    f"{upstream_id} supported_pair[{idx}] missing host-capability fields for {verification_mode}: "
                    f"{', '.join(extra_required)}"
                )

    if issues:
        sys.stderr.write("upstream-compat-matrix gate failed\n")
        for issue in issues:
            sys.stderr.write(f"- {issue}\n")
        return 1
    print("upstream-compat-matrix gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
