#!/usr/bin/env python3
"""Parse mutmut results and enforce threshold-based mutation quality gates."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MUTANT_STATUS_KEYS = ("survived", "timed_out", "suspicious", "killed")


def _normalize_status(raw: str) -> str | None:
    key = raw.strip().lower().replace(" ", "_").replace("-", "_")
    if key in MUTANT_STATUS_KEYS:
        return key
    return None


def _parse_mutmut_results(raw: str) -> dict[str, int]:
    counts = {key: 0 for key in MUTANT_STATUS_KEYS}
    for line in raw.splitlines():
        heading_match = re.match(r"^\s*([A-Za-z _-]+).*?\((\d+)\)\s*$", line)
        if heading_match:
            key = _normalize_status(heading_match.group(1))
            if key is not None:
                counts[key] += int(heading_match.group(2))
            continue
        match = re.match(r"^\s*([A-Za-z _-]+)\s*[:=]\s*(\d+)\s*$", line)
        if match:
            key = _normalize_status(match.group(1))
            if key is not None:
                counts[key] += int(match.group(2))
            continue
        lower_line = line.lower()
        if "survived" in lower_line:
            counts["survived"] += 1
        if "timed out" in lower_line or "timed_out" in lower_line:
            counts["timed_out"] += 1
        if "suspicious" in lower_line:
            counts["suspicious"] += 1
        if "killed" in lower_line:
            counts["killed"] += 1
    return counts


def _normalize_operator(raw: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", raw.strip().lower()).strip("_")
    return key


def _parse_operator_hints(raw: str) -> set[str]:
    operators: set[str] = set()
    for line in raw.splitlines():
        for match in re.finditer(r"(?:operator|mutation[_ -]?type)\s*[:=]\s*([A-Za-z0-9 _-]+)", line, flags=re.IGNORECASE):
            op = _normalize_operator(match.group(1))
            if op:
                operators.add(op)
    return operators


def _build_summary(
    counts: dict[str, int],
    operators_detected: set[str],
    expected_operators: set[str],
) -> dict[str, int | float | list[str]]:
    total = sum(counts.values())
    kill_rate = (counts["killed"] / total) if total else 0.0
    expected_count = len(expected_operators)
    detected_count = len(operators_detected)
    operator_coverage = (detected_count / expected_count) if expected_count else 0.0
    return {
        "total": total,
        "survived": counts["survived"],
        "timed_out": counts["timed_out"],
        "suspicious": counts["suspicious"],
        "killed": counts["killed"],
        "kill_rate": round(kill_rate, 4),
        "operators_detected": sorted(operators_detected),
        "operator_detected_count": detected_count,
        "operator_expected_count": expected_count,
        "operator_coverage": round(operator_coverage, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse mutmut results and enforce mutation thresholds.")
    parser.add_argument("--input", default="-", help="Mutmut result file path or '-' for stdin")
    parser.add_argument("--max-survived", type=int, default=0, help="Maximum allowed survived mutants")
    parser.add_argument("--max-timed-out", type=int, default=0, help="Maximum allowed timed_out mutants")
    parser.add_argument("--max-suspicious", type=int, default=0, help="Maximum allowed suspicious mutants")
    parser.add_argument("--min-killed", type=int, default=0, help="Minimum required killed mutants")
    parser.add_argument(
        "--require-non-empty-sample",
        action="store_true",
        help="Fail when mutation sample size is zero.",
    )
    parser.add_argument(
        "--expected-operators",
        default="",
        help="Comma-separated expected operator kinds; used to compute operator coverage",
    )
    parser.add_argument(
        "--min-operator-coverage",
        type=float,
        default=0.0,
        help="Minimum required operator coverage ratio (0.0~1.0)",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary to stdout")
    parser.add_argument("--json-output", default="", help="Write machine-readable JSON report to file path")
    args = parser.parse_args()

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"❌ mutation_report: missing input file: {input_path}")
            return 2
        raw = input_path.read_text(encoding="utf-8")

    counts = _parse_mutmut_results(raw)
    operators_detected = _parse_operator_hints(raw)
    expected_operators = {_normalize_operator(item) for item in args.expected_operators.split(",") if _normalize_operator(item)}
    summary = _build_summary(counts, operators_detected, expected_operators)
    violations: list[str] = []

    if counts["survived"] > args.max_survived:
        violations.append(f"survived={counts['survived']} > max_survived={args.max_survived}")
    if counts["timed_out"] > args.max_timed_out:
        violations.append(f"timed_out={counts['timed_out']} > max_timed_out={args.max_timed_out}")
    if counts["suspicious"] > args.max_suspicious:
        violations.append(f"suspicious={counts['suspicious']} > max_suspicious={args.max_suspicious}")
    if counts["killed"] < args.min_killed:
        violations.append(f"killed={counts['killed']} < min_killed={args.min_killed}")
    if summary["total"] == 0 and (args.require_non_empty_sample or args.min_killed > 0):
        violations.append("total_mutants=0 (no mutant samples found)")
    if summary["operator_expected_count"] > 0 and summary["operator_coverage"] < args.min_operator_coverage:
        violations.append(f"operator_coverage={summary['operator_coverage']} < min_operator_coverage={args.min_operator_coverage}")

    print(
        "mutation_report summary: "
        f"total={summary['total']} survived={summary['survived']} "
        f"timed_out={summary['timed_out']} suspicious={summary['suspicious']} "
        f"killed={summary['killed']} kill_rate={summary['kill_rate']:.2%} "
        f"operator_coverage={summary['operator_coverage']:.2%} "
        f"operators={summary['operator_detected_count']}/{summary['operator_expected_count']}"
    )

    report = {"summary": summary, "thresholds": vars(args), "violations": violations}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if violations:
        print("❌ mutation_report gate failed:")
        for item in violations:
            print(f"  - {item}")
        return 1
    print("✅ mutation_report gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
