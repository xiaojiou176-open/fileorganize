#!/usr/bin/env python3
"""Generate env-contract metrics report for CI/local gates.

This script is consumed by quality_gate and keeps write_before_search evidence
for gate observability/heartbeat-oriented governance output.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UTC_TZ = getattr(datetime, "UTC", timezone.utc)


def _load_gate_module(repo_root: Path) -> Any:
    gate_path = repo_root / "tooling" / "scripts" / "check_env_contract.py"
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


def _trend_word(delta: int) -> str:
    if delta > 0:
        return "up"
    if delta < 0:
        return "down"
    return "flat"


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


def _budget_summary(counts: dict[str, int], limits: dict[str, int]) -> str:
    parts: list[str] = []
    for prefix in sorted(limits):
        parts.append(f"{prefix}{counts.get(prefix, 0)}/{limits[prefix]}")
    return ",".join(parts)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate env contract report with trend.")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument(
        "--baseline",
        default="contracts/governance/baselines/env_contract_baseline.json",
        help="Baseline json path (repo-relative)",
    )
    parser.add_argument(
        "--output",
        default=".runtime-cache/logs/env-contract-report.json",
        help="Output json path (repo-relative)",
    )
    parser.add_argument(
        "--broad-total",
        type=int,
        default=None,
        help="Optional broad total override (governance cycle only; requires --governance-ticket)",
    )
    parser.add_argument(
        "--governance-ticket",
        default="",
        help="Required ticket/issue id when overriding broad total during governance cycle",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.broad_total is not None and not args.governance_ticket.strip():
        raise SystemExit("report broad-total override blocked: --governance-ticket is required when --broad-total is provided")
    repo_root = Path(args.root).resolve()
    module = _load_gate_module(repo_root)

    contract = set(module.ENV_CONTRACT)
    budgets = dict(module.CATEGORY_BUDGETS)
    deprecated_deadlines = dict(module.DEPRECATED_REMOVAL_DEADLINES)
    prefixes = tuple(budgets.keys())
    counts = _count_by_prefix(contract, prefixes)

    baseline_path = (repo_root / args.baseline).resolve()
    baseline: dict[str, Any] = {}
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    baseline_total = int(baseline.get("contract_total", len(contract)))
    baseline_broad_total = int(baseline.get("broad_total", 44))
    observed_business_envs = _observed_business_envs_total(module, repo_root)
    baseline_observed_business_envs = int(baseline.get("observed_business_envs", observed_business_envs))
    broad_total = int(args.broad_total) if args.broad_total is not None else baseline_broad_total
    baseline_counts = {key: int(value) for key, value in dict(baseline.get("category_counts", {})).items()}
    deltas = {prefix: counts[prefix] - baseline_counts.get(prefix, 0) for prefix in prefixes}

    report = {
        "generated_at_utc": datetime.now(UTC_TZ).isoformat(timespec="seconds"),
        "governance_ticket": args.governance_ticket.strip(),
        "contract_total": len(contract),
        "contract_total_limit": 59,
        "contract_total_delta_vs_baseline": len(contract) - baseline_total,
        "contract_total_trend": _trend_word(len(contract) - baseline_total),
        "broad_total": broad_total,
        "broad_total_delta_vs_baseline": broad_total - baseline_broad_total,
        "broad_total_trend": _trend_word(broad_total - baseline_broad_total),
        "broad_total_baseline_source": "env_contract_baseline",
        "broad_total_current_source": "arg" if args.broad_total is not None else "env_contract_baseline",
        "observed_business_envs": observed_business_envs,
        "observed_business_envs_delta_vs_baseline": observed_business_envs - baseline_observed_business_envs,
        "observed_business_envs_trend": _trend_word(observed_business_envs - baseline_observed_business_envs),
        "category_counts": counts,
        "category_limits": budgets,
        "category_deltas_vs_baseline": deltas,
        "deprecated_removal_deadlines": deprecated_deadlines,
        "baseline_path": str(Path(args.baseline)),
    }

    output_path = (repo_root / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("✅ env-contract-report: generated")
    print(f"output={output_path.relative_to(repo_root)}")
    print(
        "summary="
        f"contract_total={report['contract_total']} "
        f"contract_delta={report['contract_total_delta_vs_baseline']} "
        f"contract_trend={report['contract_total_trend']} "
        f"broad_total={report['broad_total']} "
        f"broad_delta={report['broad_total_delta_vs_baseline']} "
        f"broad_trend={report['broad_total_trend']} "
        f"observed_business_envs={report['observed_business_envs']}"
        f" observed_delta={report['observed_business_envs_delta_vs_baseline']}"
        f" observed_trend={report['observed_business_envs_trend']}"
    )
    print(
        "budget_summary="
        + _budget_summary(
            report["category_counts"],
            report["category_limits"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
UTC_TZ = getattr(datetime, "UTC", timezone.utc)
