#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
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


def _resolve(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    return candidate if candidate.is_absolute() else repo_root / candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="Require every upstream compatibility row to bind to fresh verification evidence")
    parser.add_argument("--root", default=".")
    parser.add_argument("--contract", default="contracts/upstreams/compatibility_matrix.yaml")
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    matrix = _load_yaml(repo_root / args.contract)
    issues: list[str] = []
    now = time.time()
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
            artifact_path = _resolve(repo_root, artifact_raw)
            if not artifact_path.exists():
                issues.append(f"{upstream_id} supported_pair[{idx}] missing verification artifact: {artifact_raw}")
                continue
            max_age_hours_raw = str(pair.get("verification_max_age_hours", "")).strip()
            try:
                max_age_hours = float(max_age_hours_raw)
            except ValueError:
                issues.append(f"{upstream_id} supported_pair[{idx}] invalid verification_max_age_hours: {max_age_hours_raw}")
                continue
            age_hours = (now - artifact_path.stat().st_mtime) / 3600
            if age_hours > max_age_hours:
                issues.append(
                    f"{upstream_id} supported_pair[{idx}] verification artifact is stale: "
                    f"age_hours={age_hours:.1f} max_age_hours={max_age_hours:.1f}"
                )
                continue
            payload = _load_json(artifact_path)
            if payload is None:
                issues.append(f"{upstream_id} supported_pair[{idx}] verification artifact is not valid JSON: {artifact_raw}")
                continue
            summary = payload.get("summary")
            upstream_summary = payload.get("upstream_summary")
            if not isinstance(summary, dict) or str(summary.get("overall_status", "")).strip() != "passed":
                issues.append(f"{upstream_id} supported_pair[{idx}] verification artifact is not green: {artifact_raw}")
            if not isinstance(upstream_summary, dict) or str(upstream_summary.get("status", "")).strip() != "ok":
                issues.append(
                    f"{upstream_id} supported_pair[{idx}] verification artifact missing upstream_summary ok status: {artifact_raw}"
                )

    if issues:
        print("upstream-verification-freshness gate failed", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1

    print("upstream-verification-freshness gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
