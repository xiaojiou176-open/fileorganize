#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid yaml: {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate upstream registry surfaces")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    registry = _load_yaml(root / "contracts/upstreams/upstream_registry.yaml")
    runtime_layout = _load_yaml(root / "contracts/runtime/filesystem_layout.yaml")
    missing: list[str] = []
    for key, rel in registry.get("registry", {}).items():
        if not (root / rel).exists():
            missing.append(f"{key}: {rel}")
    allowed_runtime_paths = set(str(item) for item in runtime_layout.get("repo_runtime", {}).get("allowed_paths", []))
    for key, rel in registry.get("download_roots", {}).items():
        rel_path = str(rel)
        if rel_path not in allowed_runtime_paths:
            missing.append(f"download root not whitelisted by filesystem layout: {key} -> {rel_path}")
    if missing:
        sys.stderr.write("upstream-registry-completeness gate failed\n")
        for item in missing:
            sys.stderr.write(f"- {item}\n")
        return 1
    print("upstream-registry-completeness gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
