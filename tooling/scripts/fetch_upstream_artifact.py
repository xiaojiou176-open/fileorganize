#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

import yaml


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid yaml: {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a registered upstream artifact into a managed runtime cache destination")
    parser.add_argument("--root", default=".")
    parser.add_argument("--upstream-id", required=True)
    parser.add_argument("--destination-kind", choices=("download-cache",), default="download-cache")
    parser.add_argument("--expected-sha256", default="")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    inventory = _load_yaml(root / "contracts/upstreams/upstream_inventory.yaml")
    registry = _load_yaml(root / "contracts/upstreams/upstream_registry.yaml")
    item = next(
        (entry for entry in inventory.get("upstreams", []) if isinstance(entry, dict) and entry.get("id") == args.upstream_id),
        None,
    )
    if item is None:
        raise SystemExit(f"unknown upstream-id: {args.upstream_id}")

    source_url = str(item.get("source_url", "")).strip()
    if not source_url:
        raise SystemExit(f"upstream-id missing source_url: {args.upstream_id}")

    checksum = str(item.get("checksum_or_digest", "")).strip()
    expected_sha256 = args.expected_sha256.strip()
    if checksum.startswith("sha256:"):
        expected_sha256 = checksum.split(":", 1)[1]
    if not expected_sha256:
        raise SystemExit(f"upstream-id requires checksum enforcement: {args.upstream_id}")

    download_root = root / str(dict(registry.get("download_roots", {})).get("runtime_tmp_downloads", ".runtime-cache/tmp/downloads"))
    download_root.mkdir(parents=True, exist_ok=True)
    filename = Path(source_url).name or f"{args.upstream_id}.artifact"
    output = download_root / filename
    with urlopen(source_url) as response:  # noqa: S310
        payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_sha256:
        raise SystemExit(f"sha256 mismatch for {args.upstream_id}: expected {expected_sha256}, got {digest}")
    output.write_bytes(payload)
    print(json.dumps({"status": "fetched", "upstream_id": args.upstream_id, "output": str(output.relative_to(root))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
