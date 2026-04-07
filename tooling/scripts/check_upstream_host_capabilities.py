#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid yaml: {path}")
    return payload


def _inventory_by_id(root: Path) -> dict[str, dict[str, Any]]:
    payload = _load_yaml(root / "contracts/upstreams/upstream_inventory.yaml")
    items = payload.get("upstreams", [])
    result: dict[str, dict[str, Any]] = {}
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                upstream_id = str(item.get("id", "")).strip()
                if upstream_id:
                    result[upstream_id] = item
    return result


def _pairs_by_id(root: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_yaml(root / "contracts/upstreams/compatibility_matrix.yaml")
    result: dict[str, list[dict[str, Any]]] = {}
    for entry in payload.get("matrix", []):
        if not isinstance(entry, dict):
            continue
        upstream_id = str(entry.get("upstream_id", "")).strip()
        pairs = entry.get("supported_pairs", [])
        if upstream_id and isinstance(pairs, list):
            result[upstream_id] = [pair for pair in pairs if isinstance(pair, dict)]
    return result


def _is_executable_file(path: str) -> bool:
    return Path(path).is_file() and os.access(path, os.X_OK)


def _resolve_trusted_binary(*names: str) -> str | None:
    for name in names:
        raw = shutil.which(name)
        if raw and _is_executable_file(raw):
            return str(Path(raw).resolve())
    return None


def _probe_ffmpeg() -> dict[str, Any]:
    resolved = _resolve_trusted_binary("ffmpeg")
    return {
        "status": "detected" if resolved else "missing-optional",
        "resolved_path": resolved,
    }


def _probe_document_conversion() -> dict[str, Any]:
    libreoffice = _resolve_trusted_binary("soffice", "libreoffice")
    if not libreoffice:
        macos_bundle = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        if _is_executable_file(macos_bundle):
            libreoffice = str(Path(macos_bundle).resolve())
    unoconv = _resolve_trusted_binary("unoconv")
    resolved = libreoffice or unoconv
    return {
        "status": "detected" if resolved else "missing-optional",
        "resolved_path": resolved,
        "detected_tool": "libreoffice" if libreoffice else ("unoconv" if unoconv else None),
    }


def _probe_unsupported() -> dict[str, Any]:
    return {
        "status": "unsupported-declared",
        "resolved_path": None,
    }


_PROBES = {
    "ffmpeg": _probe_ffmpeg,
    "document-conversion": _probe_document_conversion,
    "unsupported-capability": _probe_unsupported,
}


def _check_required_fields(container: dict[str, Any], fields: list[str], label: str, issues: list[str]) -> None:
    missing = [field for field in fields if not str(container.get(field, "")).strip() and container.get(field) not in (False, 0)]
    if missing:
        issues.append(f"{label} missing fields: {', '.join(missing)}")


def _check_expected(container: dict[str, Any], expected: dict[str, Any], label: str, issues: list[str]) -> None:
    for key, value in expected.items():
        if container.get(key) != value:
            issues.append(f"{label} expected {key}={value!r}, got {container.get(key)!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and probe host-managed upstream capability surfaces")
    parser.add_argument("upstream_ids", nargs="*", help="Optional subset of host-managed upstream ids to validate")
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default="contracts/upstreams/host_capability_policy.yaml")
    parser.add_argument("--json-out", default=".runtime-cache/logs/host-capability-preflight/summary.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy_path = root / args.policy if not Path(args.policy).is_absolute() else Path(args.policy)
    policy = _load_yaml(policy_path)
    inventory = _inventory_by_id(root)
    pairs_by_id = _pairs_by_id(root)

    selected = {item.strip() for item in args.upstream_ids if item.strip()}
    mode_policies = policy.get("modes", {})
    targets = policy.get("targets", [])
    issues: list[str] = []
    target_results: list[dict[str, Any]] = []

    if not isinstance(mode_policies, dict) or not isinstance(targets, list):
        raise SystemExit(f"invalid host capability policy: {policy_path}")

    for target in targets:
        if not isinstance(target, dict):
            continue
        upstream_id = str(target.get("upstream_id", "")).strip()
        if not upstream_id:
            continue
        if selected and upstream_id not in selected:
            continue

        inventory_item = inventory.get(upstream_id)
        pair_list = pairs_by_id.get(upstream_id, [])
        if inventory_item is None:
            issues.append(f"{upstream_id} missing from upstream_inventory.yaml")
            continue
        if not pair_list:
            issues.append(f"{upstream_id} missing from compatibility_matrix.yaml")
            continue

        pair = pair_list[0]
        verification_mode = str(inventory_item.get("verification_mode", "")).strip()
        mode_policy = mode_policies.get(verification_mode)
        if not isinstance(mode_policy, dict):
            issues.append(f"{upstream_id} uses unsupported verification_mode in host capability policy: {verification_mode}")
            continue

        required_inventory_fields = [str(field) for field in mode_policy.get("required_inventory_fields", [])]
        required_pair_fields = [str(field) for field in mode_policy.get("required_pair_fields", [])]
        _check_required_fields(inventory_item, required_inventory_fields, f"{upstream_id} inventory", issues)
        _check_required_fields(pair, required_pair_fields, f"{upstream_id} supported_pair", issues)
        _check_expected(inventory_item, target.get("expected_inventory", {}), f"{upstream_id} inventory", issues)
        _check_expected(pair, target.get("expected_pair", {}), f"{upstream_id} supported_pair", issues)

        probe_name = str(target.get("probe", "")).strip()
        probe = _PROBES.get(probe_name)
        if probe is None:
            issues.append(f"{upstream_id} has unknown probe: {probe_name}")
            continue
        probe_result = probe()
        allowed_missing_behavior = str(pair.get("allowed_missing_behavior", "")).strip()
        status = str(probe_result.get("status", "")).strip()
        if status == "missing-optional" and allowed_missing_behavior != "allow-and-report":
            issues.append(f"{upstream_id} probe reported missing-optional but pair does not allow-and-report")
        if status == "unsupported-declared" and allowed_missing_behavior != "declared-unsupported":
            issues.append(f"{upstream_id} probe reported unsupported-declared but pair does not declare unsupported handling")
        if status == "detected" and not str(probe_result.get("resolved_path", "")).strip():
            issues.append(f"{upstream_id} probe reported detected but resolved_path is empty")

        target_results.append(
            {
                "upstream_id": upstream_id,
                "assurance_tier": inventory_item.get("assurance_tier"),
                "repo_preflight_gate": inventory_item.get("repo_preflight_gate"),
                "verification_mode": verification_mode,
                "probe": probe_name,
                "probe_result": probe_result,
            }
        )

    summary = {
        "status": "ok" if not issues else "failed",
        "policy_path": str(policy_path),
        "checked_targets": len(target_results),
        "targets": target_results,
        "issues": issues,
    }

    json_out = Path(args.json_out)
    json_out = root / json_out if not json_out.is_absolute() else json_out
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if issues:
        print("upstream-host-capability gate failed", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1

    print("upstream-host-capability gate passed")
    print(f"summary_path={json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
