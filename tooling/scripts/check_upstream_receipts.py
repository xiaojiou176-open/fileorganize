#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid yaml: {path}")
    return data


def _load_json(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dedicated per-upstream receipt artifacts")
    parser.add_argument("--root", default=".")
    parser.add_argument("--contract", default="contracts/upstreams/compatibility_matrix.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    matrix = _load_yaml(root / args.contract)
    issues: list[str] = []
    for entry in matrix.get("matrix", []):
        if not isinstance(entry, dict):
            continue
        upstream_id = str(entry.get("upstream_id", "")).strip() or "<unknown>"
        pairs = entry.get("supported_pairs", [])
        if not isinstance(pairs, list):
            continue
        for idx, pair in enumerate(pairs, 1):
            if not isinstance(pair, dict):
                continue
            artifact_raw = str(pair.get("verification_artifact", "")).strip()
            if not artifact_raw:
                issues.append(f"{upstream_id} supported_pair[{idx}] missing verification_artifact")
                continue
            artifact_path = root / artifact_raw if not Path(artifact_raw).is_absolute() else Path(artifact_raw)
            if not artifact_path.exists():
                issues.append(f"{upstream_id} supported_pair[{idx}] receipt missing: {artifact_raw}")
                continue
            receipt = _load_json(artifact_path)
            if receipt is None:
                issues.append(f"{upstream_id} supported_pair[{idx}] receipt is not valid JSON: {artifact_raw}")
                continue
            if str(receipt.get("upstream_id", "")).strip() != upstream_id:
                issues.append(f"{upstream_id} supported_pair[{idx}] receipt upstream_id mismatch: {artifact_raw}")
            summary = receipt.get("summary")
            if not isinstance(summary, dict) or str(summary.get("overall_status", "")).strip() != "passed":
                issues.append(f"{upstream_id} supported_pair[{idx}] receipt summary not green: {artifact_raw}")
            upstream_summary = receipt.get("upstream_summary")
            if not isinstance(upstream_summary, dict) or str(upstream_summary.get("status", "")).strip() != "ok":
                issues.append(f"{upstream_id} supported_pair[{idx}] receipt upstream_summary not ok: {artifact_raw}")
                continue
            supported_pair = receipt.get("supported_pair")
            if not isinstance(supported_pair, dict):
                issues.append(f"{upstream_id} supported_pair[{idx}] receipt missing supported_pair object: {artifact_raw}")
            else:
                for key, value in pair.items():
                    if supported_pair.get(key) != value:
                        issues.append(f"{upstream_id} supported_pair[{idx}] receipt supported_pair mismatch for {key}: {artifact_raw}")
                        break
            failure_ownership = upstream_summary.get("failure_ownership")
            if not isinstance(failure_ownership, dict):
                issues.append(f"{upstream_id} supported_pair[{idx}] receipt missing failure_ownership: {artifact_raw}")
            else:
                missing = [key for key in ("owner", "failure_owner", "escalation") if not str(failure_ownership.get(key, "")).strip()]
                if missing:
                    issues.append(
                        f"{upstream_id} supported_pair[{idx}] receipt failure_ownership missing fields {', '.join(missing)}: {artifact_raw}"
                    )

    if issues:
        sys.stderr.write("upstream-receipts gate failed\n")
        for issue in issues:
            sys.stderr.write(f"- {issue}\n")
        return 1

    print("upstream-receipts gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
