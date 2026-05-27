#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def _load_inventory(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid upstream inventory: {path}")
    return data


def _resolve_command(root: Path, upstream_id: str) -> list[str]:
    if upstream_id == "python-runtime-lock":
        return ["bash", "tooling/upstreams/upgrade_deps.sh", "python"]
    if upstream_id == "node-lock":
        return ["npm", "--prefix", "apps/webui", "update", "--package-lock-only"]
    raise SystemExit(f"execute mode unsupported for upstream_id={upstream_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run or execute a single upstream upgrade")
    parser.add_argument("--root", default=".")
    parser.add_argument("--inventory", default="contracts/upstreams/upstream_inventory.yaml")
    parser.add_argument("--upstream-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if args.dry_run == args.execute:
        raise SystemExit("choose exactly one of --dry-run or --execute")

    root = Path(args.root).resolve()
    inventory = _load_inventory(root / args.inventory)
    item = next((u for u in inventory.get("upstreams", []) if isinstance(u, dict) and u.get("id") == args.upstream_id), None)
    if item is None:
        raise SystemExit(f"unknown upstream_id: {args.upstream_id}")

    command = _resolve_command(root, args.upstream_id)
    receipt = {
        "upstream_id": args.upstream_id,
        "verification_suite": item.get("verification_suite"),
        "rollback_strategy": item.get("rollback_strategy"),
        "failure_domain": item.get("failure_domain"),
        "command": command,
        "mode": "dry-run" if args.dry_run else "execute",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if args.execute:
        subprocess.run(command, cwd=root, check=True)
        receipt_dir = root / ".runtime-cache" / "logs" / "upstream-upgrade"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        receipt_path = receipt_dir / f"{args.upstream_id}-{stamp}.json"
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        receipt["receipt_path"] = str(receipt_path.relative_to(root))

    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
