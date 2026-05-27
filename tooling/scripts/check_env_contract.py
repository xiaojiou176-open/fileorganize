#!/usr/bin/env python3
"""Gate: business env variables read by code must exist in env_contract.

This guard runs in pre-push/local_quality_gate/quality_gate/CI flows.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from docs_render_lib import env_contract_variables, load_env_contract_registry

REPO_ROOT = Path(__file__).resolve().parents[2]
ZERO_SHA = "0" * 40
TARGET_EXTENSIONS = {".py", ".sh"}
DEFAULT_SCAN_PATHS = (
    "apps/api",
    "apps/cli",
    "packages/domain",
    "packages/application",
    "packages/infrastructure",
    "packages/observability",
    "tooling/scripts",
)
ENV_REGISTRY = load_env_contract_registry(REPO_ROOT)
BUSINESS_ENV_PREFIXES = tuple(str(item) for item in ENV_REGISTRY.get("business_env_prefixes", []))
IGNORED_SUFFIXES = tuple(str(item) for item in ENV_REGISTRY.get("ignored_suffixes", []))
ENV_CONTRACT = env_contract_variables(ENV_REGISTRY)
CATEGORY_BUDGETS = {str(prefix): int(limit) for prefix, limit in dict(ENV_REGISTRY.get("category_budgets", {})).items()}
DEPRECATED_REMOVAL_DEADLINES: dict[str, str] = {
    str(name): str(due) for name, due in dict(ENV_REGISTRY.get("deprecated_removal_deadlines", {})).items()
}
FORBIDDEN_ENV_EXAMPLE_KEYS = {str(name) for name in ENV_REGISTRY.get("forbidden_env_example_keys", [])}

PY_ENV_PATTERNS = (
    re.compile(r"""os\.environ\.get\(\s*["']([A-Z][A-Z0-9_]+)["']"""),
    re.compile(r"""os\.environ\[\s*["']([A-Z][A-Z0-9_]+)["']\s*]"""),
    re.compile(r"""os\.getenv\(\s*["']([A-Z][A-Z0-9_]+)["']"""),
    re.compile(r"""(?<!\.)getenv\(\s*["']([A-Z][A-Z0-9_]+)["']"""),
)
SH_ENV_PATTERNS = (
    re.compile(r"""\$\{([A-Z][A-Z0-9_]+)(?::[-=?+][^}]*)?}"""),
    re.compile(r"""(?<![A-Za-z0-9_{])\$([A-Z][A-Z0-9_]+)\b"""),
)
ENV_EXAMPLE_PATTERN = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]+)\s*=")
UTC_TZ = getattr(datetime, "UTC", timezone.utc)


def _run_git(repo_root: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _resolve_pre_push_range(repo_root: Path) -> tuple[str, str] | None:
    from_ref = os.getenv("PRE_COMMIT_FROM_REF", "").strip()
    to_ref = os.getenv("PRE_COMMIT_TO_REF", "").strip() or "HEAD"
    if from_ref and from_ref != ZERO_SHA:
        return from_ref, to_ref

    upstream = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
    if not upstream:
        return None
    base = _run_git(repo_root, ["merge-base", "HEAD", upstream])
    if not base:
        return None
    return base, "HEAD"


def _changed_files(repo_root: Path, mode: str, diff_base: str, diff_head: str) -> set[Path]:
    if mode == "all":
        return set()

    if mode == "staged":
        out = _run_git(repo_root, ["diff", "--cached", "--name-only"])
    elif mode == "working-tree":
        out = _run_git(repo_root, ["diff", "--name-only"])
    elif mode == "diff-range":
        out = _run_git(repo_root, ["diff", "--name-only", f"{diff_base}...{diff_head}"])
    else:
        pre_push_range = _resolve_pre_push_range(repo_root)
        if pre_push_range is not None:
            base, head = pre_push_range
            out = _run_git(repo_root, ["diff", "--name-only", f"{base}...{head}"])
        else:
            staged_out = _run_git(repo_root, ["diff", "--cached", "--name-only"])
            working_out = _run_git(repo_root, ["diff", "--name-only"])
            untracked_out = _run_git(repo_root, ["ls-files", "--others", "--exclude-standard"])
            if staged_out or working_out or untracked_out:
                out = "\n".join(chunk for chunk in (staged_out, working_out, untracked_out) if chunk)
            else:
                out = _run_git(repo_root, ["diff", "--name-only", "HEAD~1", "HEAD"])

    changed: set[Path] = set()
    for line in out.splitlines():
        rel = line.strip()
        if not rel:
            continue
        changed.add((repo_root / rel).resolve())
    return changed


def _iter_target_files(repo_root: Path, scan_paths: tuple[str, ...], changed_files: set[Path]) -> list[Path]:
    files: list[Path] = []
    for raw in scan_paths:
        base = (repo_root / raw).resolve()
        if not base.exists():
            continue
        if base.is_file() and base.suffix in TARGET_EXTENSIONS:
            files.append(base)
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in TARGET_EXTENSIONS:
                continue
            files.append(path.resolve())
    if not changed_files:
        return files
    return [path for path in files if path in changed_files]


def _extract_env_refs(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    patterns = PY_ENV_PATTERNS if path.suffix == ".py" else SH_ENV_PATTERNS
    refs: list[tuple[int, str]] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        for pattern in patterns:
            for match in pattern.finditer(raw_line):
                refs.append((line_no, match.group(1)))
    return refs


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ensure business env reads are registered in env_contract.",
    )
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument(
        "--mode",
        choices=("auto", "all", "staged", "working-tree", "diff-range"),
        default="auto",
        help="Changed-file selection mode",
    )
    parser.add_argument("--diff-base", default="", help="Diff base for diff-range mode")
    parser.add_argument("--diff-head", default="HEAD", help="Diff head for diff-range mode")
    parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Additional scan path (can be repeated)",
    )
    parser.add_argument(
        "--max-contract-size",
        type=int,
        default=int(os.getenv("ENV_CONTRACT_MAX_SIZE", "59")),
        help="Max allowed env vars in ENV_CONTRACT (default: 59 or ENV_CONTRACT_MAX_SIZE)",
    )
    parser.add_argument(
        "--category-budget",
        action="append",
        default=[],
        help="Override category budget in format PREFIX=INT (can be repeated)",
    )
    parser.add_argument(
        "--today",
        default="",
        help="Override current date (YYYY-MM-DD) for deterministic checks/tests",
    )
    return parser.parse_args()


def _extract_env_example_keys(env_example_path: Path) -> set[str]:
    keys: set[str] = set()
    if not env_example_path.exists():
        return keys
    for raw_line in env_example_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = ENV_EXAMPLE_PATTERN.match(raw_line)
        if match:
            keys.add(match.group(1))
    return keys


def _parse_category_budget_overrides(raw_items: list[str]) -> dict[str, int]:
    overrides: dict[str, int] = {}
    for item in raw_items:
        if "=" not in item:
            raise ValueError(f"invalid --category-budget value: {item!r}")
        prefix, raw_value = item.split("=", 1)
        prefix = prefix.strip()
        if not prefix or not prefix.endswith("_"):
            raise ValueError(f"category prefix must end with '_': {prefix!r}")
        value = int(raw_value.strip())
        if value < 0:
            raise ValueError(f"category budget must be >= 0: {item!r}")
        overrides[prefix] = value
    return overrides


def _count_by_prefix(contract: set[str], prefixes: tuple[str, ...]) -> dict[str, int]:
    counts = {prefix: 0 for prefix in prefixes}
    for name in contract:
        for prefix in prefixes:
            if name.startswith(prefix):
                counts[prefix] += 1
                break
    return counts


def main() -> int:
    args = _parse_args()
    if args.mode == "diff-range" and not args.diff_base:
        print("❌ env_contract: --diff-base is required when --mode=diff-range", file=sys.stderr)
        return 2

    repo_root = Path(args.root).resolve()
    if len(ENV_CONTRACT) > args.max_contract_size:
        print(f"❌ env_contract: contract size exceeded (current={len(ENV_CONTRACT)}, max={args.max_contract_size})")
        print("fix: merge/reduce env vars or explicitly raise --max-contract-size with documented rationale")
        return 1

    try:
        budget_overrides = _parse_category_budget_overrides(args.category_budget)
    except ValueError as exc:
        print(f"❌ env_contract: {exc}", file=sys.stderr)
        return 2

    category_budgets = dict(CATEGORY_BUDGETS)
    category_budgets.update(budget_overrides)
    category_prefixes = tuple(category_budgets.keys())
    category_counts = _count_by_prefix(ENV_CONTRACT, category_prefixes)
    exceeded = [
        (prefix, category_counts[prefix], category_budgets[prefix])
        for prefix in category_prefixes
        if category_counts[prefix] > category_budgets[prefix]
    ]
    if exceeded:
        print("❌ env_contract: category budget exceeded")
        for prefix, count, limit in exceeded:
            print(f"- {prefix}: current={count}, limit={limit}")
        print("fix: merge/reduce vars in exceeded categories or adjust budget with documented rationale")
        return 1

    if args.today:
        try:
            today = date.fromisoformat(args.today)
        except ValueError:
            print(f"❌ env_contract: invalid --today date: {args.today!r}", file=sys.stderr)
            return 2
    else:
        today = datetime.now(UTC_TZ).date()

    expired_not_removed: list[tuple[str, str]] = []
    for name, due in DEPRECATED_REMOVAL_DEADLINES.items():
        due_date = date.fromisoformat(due)
        if today >= due_date and name in ENV_CONTRACT:
            expired_not_removed.append((name, due))

    if expired_not_removed:
        print("❌ env_contract: deprecated vars reached removal deadline")
        for name, due in expired_not_removed:
            print(f"- {name}: due={due}")
        print("fix: remove expired deprecated vars from ENV_CONTRACT/.env.example/docs and migration paths")
        return 1

    env_example_path = repo_root / ".env.example"
    env_example_keys = _extract_env_example_keys(env_example_path)
    if env_example_path.exists():
        forbidden_in_env_example = sorted(name for name in FORBIDDEN_ENV_EXAMPLE_KEYS if name in env_example_keys)
        if forbidden_in_env_example:
            print("❌ env_contract: .env.example contains forbidden legacy/example keys")
            for name in forbidden_in_env_example:
                print(f"- {name}")
            print("fix: remove forbidden keys from .env.example and keep only contract/runtime keys")
            return 1

        unexpected_in_env_example = sorted(name for name in env_example_keys if name not in ENV_CONTRACT)
        if unexpected_in_env_example:
            print("❌ env_contract: .env.example contains non-contract keys")
            for name in unexpected_in_env_example:
                print(f"- {name}")
            print("fix: keep only contract/runtime keys in .env.example (or register in ENV_CONTRACT if truly required)")
            return 1

        missing_in_env_example = sorted(name for name in ENV_CONTRACT if name not in env_example_keys)
        if missing_in_env_example:
            print("❌ env_contract: .env.example is missing contract keys")
            for name in missing_in_env_example:
                print(f"- {name}")
            print("fix: add missing keys (commented or active) into .env.example")
            return 1

    changed = _changed_files(repo_root, args.mode, args.diff_base, args.diff_head)
    scan_paths = tuple(args.scan_path) if args.scan_path else DEFAULT_SCAN_PATHS
    targets = _iter_target_files(repo_root, scan_paths, changed)

    if args.mode != "all" and not targets:
        print(f"env_contract: no in-scope changes for mode={args.mode}, skip")
        return 0

    observed: dict[str, list[str]] = {}
    for path in targets:
        rel = path.relative_to(repo_root).as_posix()
        for line_no, env_name in _extract_env_refs(path):
            if not env_name.startswith(BUSINESS_ENV_PREFIXES):
                continue
            if env_name.endswith(IGNORED_SUFFIXES):
                continue
            observed.setdefault(env_name, []).append(f"{rel}:{line_no}")

    missing = sorted(name for name in observed if name not in ENV_CONTRACT)
    if missing:
        print("❌ env_contract: found business env reads not registered in env_contract")
        for name in missing:
            locations = ", ".join(observed[name][:5])
            print(f"- {name}: {locations}")
        print("fix: add missing env names into contracts/runtime/env_contract_registry.yaml and re-render docs")
        return 1

    print("✅ env_contract: passed")
    print(f"checked_files={len(targets)}")
    print(f"observed_business_envs={len(observed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
