#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    from packages.domain.strategy_pack_registry import load_strategy_packs

    parser = argparse.ArgumentParser(description="Validate repo-shipped strategy packs")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    packs = load_strategy_packs(repo_root)
    issues: list[str] = []
    if not packs:
        issues.append("no strategy packs found under contracts/strategies")

    seen_ids: set[str] = set()
    for pack in packs:
        if not pack.id:
            issues.append("strategy pack missing id")
        if pack.id in seen_ids:
            issues.append(f"duplicate strategy pack id: {pack.id}")
        seen_ids.add(pack.id)
        if not pack.name:
            issues.append(f"strategy pack missing name: {pack.id}")
        if not pack.categories:
            issues.append(f"strategy pack missing categories: {pack.id}")
        if pack.review_confidence_threshold <= 0:
            issues.append(f"strategy pack invalid review threshold: {pack.id}")

    if issues:
        sys.stderr.write("strategy-pack-registry gate failed\n")
        for item in issues:
            sys.stderr.write(f"- {item}\n")
        return 1

    print("strategy-pack-registry gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
