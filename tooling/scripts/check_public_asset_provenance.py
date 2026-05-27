#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def _load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid public asset provenance contract: {path}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 64), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate public asset / fixture provenance against the repo contract")
    parser.add_argument("--root", default=".")
    parser.add_argument("--contract", default="contracts/governance/public_asset_provenance.yaml")
    parser.add_argument("--policy", default="contracts/governance/public_readiness_policy.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    contract = _load_yaml(root / args.contract)
    policy = _load_yaml(root / args.policy)
    entries = contract.get("assets", [])
    required_paths = [str(item) for item in policy.get("required_asset_provenance_entries", [])]
    errors: list[str] = []

    if not isinstance(entries, list):
        raise SystemExit("invalid public asset provenance contract: assets must be a list")

    declared_paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("public asset provenance entry must be an object")
            continue
        rel = str(entry.get("path", "")).strip()
        kind = str(entry.get("kind", "")).strip()
        status = str(entry.get("status", "")).strip()
        license_name = str(entry.get("license", "")).strip()
        sha256 = str(entry.get("sha256", "")).strip()
        notes = str(entry.get("notes", "")).strip()
        file_size = entry.get("file_size_bytes")

        if not rel:
            errors.append("public asset provenance entry missing path")
            continue
        declared_paths.add(rel)
        path = root / rel
        if not path.exists() or not path.is_file():
            errors.append(f"missing public asset / fixture path: {rel}")
            continue
        if not kind:
            errors.append(f"{rel}: missing kind")
        if not status:
            errors.append(f"{rel}: missing status")
        if not license_name:
            errors.append(f"{rel}: missing license")
        if not notes:
            errors.append(f"{rel}: missing notes")
        if not sha256:
            errors.append(f"{rel}: missing sha256")
        elif _sha256(path) != sha256:
            errors.append(f"{rel}: sha256 drifted from provenance contract")
        if not isinstance(file_size, int):
            errors.append(f"{rel}: file_size_bytes must be an integer")
        elif path.stat().st_size != file_size:
            errors.append(f"{rel}: file_size_bytes drifted from provenance contract")

    for rel in required_paths:
        if rel not in declared_paths:
            errors.append(f"required asset provenance entry missing: {rel}")

    if errors:
        print("❌ public-asset-provenance: failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print("✅ public-asset-provenance: passed")
    print(f"checked_assets={len(declared_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
