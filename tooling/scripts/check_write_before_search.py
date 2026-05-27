#!/usr/bin/env python3
"""Enforce executable "search before write" policy with ripgrep evidence."""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path

ZERO_SHA = "0" * 40

SCOPE_PATTERNS = (
    "apps/api/*.py",
    "apps/api/**/*.py",
    "tooling/*.md",
    "tooling/**/*.md",
    "tooling/runtime/*.sh",
    "tooling/gates/*.sh",
    "tooling/docs/*.sh",
    "tooling/docs/*.py",
    "tooling/cleanup/*.sh",
    "tooling/ci/*.sh",
    "tooling/upstreams/*.sh",
    "tooling/upstreams/*.py",
    "tooling/scripts/*.sh",
    "tooling/scripts/*.py",
    "tooling/scripts/**/*.py",
    "tests/*.py",
    "tests/**/*.py",
    "tests/*.md",
    "tests/**/*.md",
    "docs/*.md",
    "docs/**/*.md",
    "AGENTS.md",
    "CLAUDE.md",
    "apps/api/AGENTS.md",
    "apps/api/CLAUDE.md",
    "tests/AGENTS.md",
    "tests/CLAUDE.md",
    "docs/AGENTS.md",
    "docs/CLAUDE.md",
    "apps/webui/src/*.ts",
    "apps/webui/src/**/*.ts",
    "apps/webui/src/*.tsx",
    "apps/webui/src/**/*.tsx",
    "apps/webui/src/*.js",
    "apps/webui/src/**/*.js",
    "apps/webui/src/*.jsx",
    "apps/webui/src/**/*.jsx",
    "apps/webui/src/*.css",
    "apps/webui/src/**/*.css",
    "apps/webui/index.html",
    "apps/webui/package.json",
    "apps/webui/package-lock.json",
    "apps/webui/tsconfig*.json",
    "apps/webui/vite.config.ts",
    "apps/webui/eslint.config.js",
    "apps/webui/tailwind.config.js",
    "apps/webui/postcss.config.js",
    "apps/webui/components.json",
    "apps/webui/README.md",
    "apps/webui/AGENTS.md",
    "apps/webui/CLAUDE.md",
)

SEARCH_TARGETS = (
    "apps/api",
    "apps/cli",
    "packages/domain",
    "packages/application",
    "packages/infrastructure",
    "packages/observability",
    "tooling",
    "tests",
    "docs",
    "apps/webui",
    "AGENTS.md",
    "CLAUDE.md",
)

MODULE_REQUIREMENTS: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    (
        "pipeline",
        r"(analyze|apply|rollback|report|manifest|wal|schema|log)",
        ("apps/api/", "apps/cli/", "packages/domain/", "packages/application/", "packages/infrastructure/", "packages/observability/"),
        "pipeline 变更必须包含核心流程或事实源关键词",
    ),
    (
        "scripts",
        r"(quality_gate|doc_drift|write_before_search|no_logs_no_merge|heartbeat|pre-commit|pre-push)",
        ("tooling/",),
        "scripts 变更必须体现门禁、并发或可观测关键词",
    ),
    (
        "tests",
        r"(pytest|test_|unit|e2e|fixture|assert|write_before_search|no_logs_no_merge|质量门禁|写前必搜)",
        ("tests/",),
        "tests 变更必须体现测试门禁与复用策略关键词",
    ),
    (
        "docs",
        (
            r"(导航|Navigation|按需加载|lazy-load|写前必搜|search-before-write|"
            r"可执行门禁|executable gate|No Logs No Merge|logging_observability)"
        ),
        ("docs/",),
        "docs 变更必须包含导航、lazy-load、search-before-write 或门禁关键词",
    ),
    (
        "apps/webui",
        r"(route|page|component|hook|api|job|manifest|report|rollback|analyze|apply|webui|UI|ui)",
        ("apps/webui/",),
        "webui 变更必须体现页面、路由、组件或核心流程关键词",
    ),
    (
        "root-guides",
        (
            r"(项目目的|Project purpose|技术栈|Tech stack|导航手册|Navigation|"
            r"按需加载|lazy-load|写前必搜|search-before-write|可执行门禁|executable gate)"
        ),
        ("AGENTS.md", "CLAUDE.md"),
        "根级指南变更必须保持 AI 导航与执行约束字段",
    ),
)


def _run(repo_root: Path, args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=check,
    )


def _run_git(repo_root: Path, args: list[str]) -> str:
    proc = _run(repo_root, ["git", "-c", "core.quotepath=false", *args])
    if proc.returncode != 0:
        return ""
    return proc.stdout


def _run_git_ref(repo_root: Path, args: list[str]) -> str:
    return _run_git(repo_root, args).strip()


def _resolve_pre_push_range(repo_root: Path) -> tuple[str, str] | None:
    from_ref = _env("PRE_COMMIT_FROM_REF")
    to_ref = _env("PRE_COMMIT_TO_REF") or "HEAD"
    if from_ref and from_ref != ZERO_SHA:
        return from_ref, to_ref

    upstream = _run_git_ref(repo_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
    if not upstream:
        return None

    base = _run_git_ref(repo_root, ["merge-base", "HEAD", upstream])
    if not base:
        return None
    return base, "HEAD"


def _env(name: str) -> str:
    return str(os.environ.get(name, "")).strip()


def _normalize_paths(repo_root: Path, files: list[str]) -> list[str]:
    normalized: list[str] = []
    for item in files:
        rel = item.strip()
        if not rel:
            continue
        try:
            rel_path = Path(rel).resolve().relative_to(repo_root.resolve())
            normalized.append(rel_path.as_posix())
        except Exception:
            normalized.append(rel.replace("\\", "/"))
    return normalized


def _changed_files(repo_root: Path, mode: str, diff_base: str, diff_head: str) -> list[str]:
    if mode == "all":
        return []
    if mode == "staged":
        return _normalize_paths(repo_root, _run_git(repo_root, ["diff", "--cached", "--name-only"]).splitlines())
    if mode == "working-tree":
        return _normalize_paths(repo_root, _run_git(repo_root, ["diff", "--name-only"]).splitlines())
    if mode == "diff-range":
        return _normalize_paths(repo_root, _run_git(repo_root, ["diff", "--name-only", f"{diff_base}...{diff_head}"]).splitlines())

    pre_push_range = _resolve_pre_push_range(repo_root)
    if pre_push_range is not None:
        base, head = pre_push_range
        return _normalize_paths(repo_root, _run_git(repo_root, ["diff", "--name-only", f"{base}...{head}"]).splitlines())

    staged = _normalize_paths(repo_root, _run_git(repo_root, ["diff", "--cached", "--name-only"]).splitlines())
    working = _normalize_paths(repo_root, _run_git(repo_root, ["diff", "--name-only"]).splitlines())
    untracked = _normalize_paths(repo_root, _run_git(repo_root, ["ls-files", "--others", "--exclude-standard"]).splitlines())
    combined = list(dict.fromkeys([*staged, *working, *untracked]))
    if combined:
        return combined
    return _normalize_paths(repo_root, _run_git(repo_root, ["diff", "--name-only", "HEAD~1", "HEAD"]).splitlines())


def _in_scope(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in SCOPE_PATTERNS)


def _module_targets(repo_root: Path, scoped: list[str], prefixes: tuple[str, ...]) -> list[str]:
    targets: list[str] = []
    for path in scoped:
        if any(path.startswith(prefix) for prefix in prefixes):
            if (repo_root / path).exists():
                targets.append(path)
    return targets


def _has_rg(repo_root: Path) -> bool:
    try:
        proc = _run(repo_root, ["rg", "--version"])
    except FileNotFoundError:
        return False
    return proc.returncode == 0


def _iter_target_files(repo_root: Path, targets: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        candidate = (repo_root / target).resolve()
        if not candidate.exists():
            continue
        if candidate.is_file():
            files.append(candidate)
            continue
        for path in candidate.rglob("*"):
            if path.is_file():
                files.append(path)
    return files


def _existing_search_targets(repo_root: Path) -> list[str]:
    existing: list[str] = []
    for target in SEARCH_TARGETS:
        if (repo_root / target).exists():
            existing.append(target)
    return existing


def _python_scan(targets: list[Path], pattern: str) -> int:
    try:
        regex = re.compile(pattern)
    except re.error:
        return -1
    matches = 0
    for file in targets:
        try:
            text = file.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        for line in text.splitlines():
            if regex.search(line):
                matches += 1
    return matches


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check executable write-before-search proof via ripgrep commands.",
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
        "--keywords",
        default="analyze|apply|rollback|report|manifest|log_event|quality_gate|doc_drift",
        help="Regex keywords used for rg -n search",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.mode == "diff-range" and not args.diff_base:
        print("❌ write_before_search: --diff-base is required when --mode=diff-range", file=sys.stderr)
        return 2

    repo_root = Path(args.root).resolve()
    changed = _changed_files(repo_root, args.mode, args.diff_base, args.diff_head)
    scoped = sorted({path for path in changed if _in_scope(path)})
    if args.mode != "all" and not scoped:
        print(f"write_before_search: no in-scope changes for mode={args.mode}, skip")
        return 0

    existing_targets = _existing_search_targets(repo_root)
    if not existing_targets:
        print("❌ write_before_search: no existing search targets found", file=sys.stderr)
        return 1

    use_rg = _has_rg(repo_root)
    indexed_files = 0
    matched_lines = 0
    if use_rg:
        files_proc = _run(repo_root, ["rg", "--files", *existing_targets])
        if files_proc.returncode != 0:
            print("❌ write_before_search: failed to run `rg --files` (is ripgrep installed?)", file=sys.stderr)
            return 1
        grep_proc = _run(repo_root, ["rg", "-n", args.keywords, *existing_targets])
        if grep_proc.returncode not in (0, 1):
            print("❌ write_before_search: failed to run `rg -n`", file=sys.stderr)
            return 1
        if grep_proc.returncode == 1:
            print("❌ write_before_search: no matches for required `rg -n` keyword scan")
            print(f"keywords={args.keywords}")
            return 1
        indexed_files = len([line for line in files_proc.stdout.splitlines() if line.strip()])
        matched_lines = len([line for line in grep_proc.stdout.splitlines() if line.strip()])
    else:
        targets = _iter_target_files(repo_root, tuple(existing_targets))
        indexed_files = len(targets)
        matched_lines = _python_scan(targets, args.keywords)
        if matched_lines < 0:
            print("❌ write_before_search: invalid keyword regex pattern")
            print(f"keywords={args.keywords}")
            return 1
        if matched_lines == 0:
            print("❌ write_before_search: no matches for required `rg -n` keyword scan")
            print(f"keywords={args.keywords}")
            return 1

    missing_modules: list[str] = []
    if scoped:
        for module_name, pattern, prefixes, reason in MODULE_REQUIREMENTS:
            module_targets = _module_targets(repo_root, scoped, prefixes)
            if not module_targets:
                continue
            if use_rg:
                module_scan = _run(repo_root, ["rg", "-n", pattern, *module_targets])
                if module_scan.returncode not in (0, 1):
                    print(f"❌ write_before_search: module scan failed for {module_name}", file=sys.stderr)
                    return 1
                if module_scan.returncode == 1:
                    missing_modules.append(f"{module_name}: {reason}")
            else:
                module_files = [(repo_root / item) for item in module_targets]
                module_matches = _python_scan(module_files, pattern)
                if module_matches < 0:
                    print(f"❌ write_before_search: invalid module regex for {module_name}", file=sys.stderr)
                    return 1
                if module_matches == 0:
                    missing_modules.append(f"{module_name}: {reason}")

    if missing_modules:
        print("❌ write_before_search: missing module-level search evidence")
        for item in missing_modules:
            print(f"- {item}")
        return 1

    print("✅ write_before_search: passed")
    print(f"indexed_files={indexed_files}")
    print(f"matched_lines={matched_lines}")
    if scoped:
        print("in_scope_changes=" + ",".join(scoped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
