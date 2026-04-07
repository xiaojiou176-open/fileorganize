#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

TRACKED_OVERRIDE_SURFACES = (
    "package.json",
    "apps/webui/package.json",
)


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid yaml payload: {path}")
    return payload


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid json payload: {path}")
    return payload


def _collect_overrides(repo_root: Path) -> dict[tuple[str, str], str]:
    overrides: dict[tuple[str, str], str] = {}
    for rel_path in TRACKED_OVERRIDE_SURFACES:
        payload = _load_json(repo_root / rel_path)
        raw = payload.get("overrides", {})
        if not isinstance(raw, dict):
            raise SystemExit(f"{rel_path}: overrides must be an object when present")
        for target, value in raw.items():
            if isinstance(target, str) and isinstance(value, str):
                overrides[(rel_path, target)] = value
    return overrides


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-close when npm override surfaces drift from contracts/upstreams/patch_registry.yaml."
    )
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    registry_path = repo_root / "contracts" / "upstreams" / "patch_registry.yaml"
    registry = _load_yaml(registry_path)
    patches = registry.get("patches", [])
    if not isinstance(patches, list):
        raise SystemExit("contracts/upstreams/patch_registry.yaml: patches must be a list")

    actual_overrides = _collect_overrides(repo_root)
    declared_overrides: dict[tuple[str, str], str] = {}
    errors: list[str] = []

    for entry in patches:
        if not isinstance(entry, dict):
            errors.append("patch_registry entry must be an object")
            continue
        surface = str(entry.get("surface", "")).strip()
        target = str(entry.get("target", "")).strip()
        pinned_value = str(entry.get("pinned_value", "")).strip()
        entry_id = str(entry.get("id", "<missing-id>")).strip()

        if not surface or not target or not pinned_value:
            errors.append(f"{entry_id}: surface/target/pinned_value must all be non-empty")
            continue
        if surface not in TRACKED_OVERRIDE_SURFACES:
            errors.append(f"{entry_id}: unsupported surface {surface}")
            continue

        declared_overrides[(surface, target)] = pinned_value
        actual_value = actual_overrides.get((surface, target))
        if actual_value is None:
            errors.append(f"{entry_id}: missing override {target} in {surface}")
            continue
        if actual_value != pinned_value:
            errors.append(f"{entry_id}: pinned_value drift for {surface} -> {target} (registry={pinned_value}, actual={actual_value})")

    for key, actual_value in sorted(actual_overrides.items()):
        if key not in declared_overrides:
            surface, target = key
            errors.append(f"unregistered override {surface} -> {target}={actual_value}")

    if errors:
        print("patch-registry-alignment failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("patch-registry-alignment passed")
    for (surface, target), value in sorted(actual_overrides.items()):
        print(f"- {surface}: {target}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
