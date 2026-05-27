#!/usr/bin/env python3
"""Update env-contract baseline (governance cycle only) for pre-commit gate observability."""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_gate_module(repo_root: Path) -> Any:
    modern_gate_path = repo_root / "tooling" / "scripts" / "check_env_contract.py"
    legacy_gate_path = repo_root / "脚本" / "scripts" / "check_env_contract.py"
    gate_path = modern_gate_path if modern_gate_path.exists() else legacy_gate_path
    spec = importlib.util.spec_from_file_location("check_env_contract_gate", gate_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load gate module: {gate_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _count_by_prefix(contract: set[str], prefixes: tuple[str, ...]) -> dict[str, int]:
    counts = {prefix: 0 for prefix in prefixes}
    for name in contract:
        for prefix in prefixes:
            if name.startswith(prefix):
                counts[prefix] += 1
                break
    return counts


def _observed_business_envs_total(module: Any, repo_root: Path) -> int:
    scan_paths = tuple(module.DEFAULT_SCAN_PATHS)
    targets = module._iter_target_files(repo_root, scan_paths, set())
    observed: set[str] = set()
    for path in targets:
        for _, env_name in module._extract_env_refs(path):
            if not env_name.startswith(module.BUSINESS_ENV_PREFIXES):
                continue
            if env_name.endswith(module.IGNORED_SUFFIXES):
                continue
            observed.add(env_name)
    return len(observed)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument(
        "--baseline",
        default="contracts/governance/baselines/env_contract_baseline.json",
        help="Baseline json path (repo-relative)",
    )
    parser.add_argument(
        "--governance-ticket",
        default="",
        help="Required ticket/issue id for governance-cycle baseline updates",
    )
    parser.add_argument(
        "--broad-total",
        type=int,
        required=True,
        help="Broad metric baseline total (Phase 0 frozen value or approved new baseline)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.governance_ticket.strip():
        raise SystemExit("baseline update blocked: --governance-ticket is required")

    repo_root = Path(args.root).resolve()
    module = _load_gate_module(repo_root)
    contract = set(module.ENV_CONTRACT)
    budgets = dict(module.CATEGORY_BUDGETS)
    category_counts = _count_by_prefix(contract, tuple(budgets.keys()))
    observed_business_envs = _observed_business_envs_total(module, repo_root)

    payload = {
        "contract_total": len(contract),
        "broad_total": int(args.broad_total),
        "observed_business_envs": observed_business_envs,
        "baseline_update_policy": "governance-cycle-only",
        "governance_ticket": args.governance_ticket.strip(),
        "updated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "category_counts": category_counts,
    }
    baseline_path = (repo_root / args.baseline).resolve()
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("✅ env-contract-baseline: updated")
    print(f"output={baseline_path.relative_to(repo_root)}")
    print(
        f"contract_total={payload['contract_total']} "
        f"broad_total={payload['broad_total']} "
        f"observed_business_envs={payload['observed_business_envs']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
