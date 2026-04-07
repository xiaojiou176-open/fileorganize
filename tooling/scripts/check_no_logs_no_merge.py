#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

LOW_QUALITY_PATTERNS = (
    "something went wrong",
    "unknown error",
    "unexpected error",
    "error occurred",
    "未知错误",
    "发生错误",
    "出错了",
)
LOW_QUALITY_EVENT_NAMES = {
    "error",
    "errors",
    "unknown",
    "unknown_error",
    "unknown.error",
    "fail",
    "failed",
    "exception",
    "event",
}
ALLOW_LOW_QUALITY_MARKER = "no-logs-gate: allow-low-quality"

TARGET_EXTENSIONS = {".py", ".sh", ".yml", ".yaml", ".ts", ".tsx", ".js", ".jsx"}
DEFAULT_SCAN_PATHS = (
    "apps/api",
    "apps/cli",
    "packages/domain",
    "packages/application",
    "packages/infrastructure",
    "packages/observability",
    "tooling/scripts",
    "tests",
    "apps/webui/src",
    ".github/workflows",
)

EXCEPTION_CONTEXT_FIELDS = (
    "exception",
    "exc",
    "exc_info",
    "traceback",
    "stack",
)
REQUIRED_LOG_CONTEXT_FIELDS = (
    "trace_id",
    "module",
    "action",
    "status",
)
EVENTS_REQUIRE_DURATION_SUFFIXES = (
    ".end",
    "_end",
    ".done",
    "_done",
    ".finish",
    "_finish",
    ".complete",
    "_complete",
    ".completed",
    "_completed",
)
ZERO_SHA = "0" * 40


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    rule: str
    snippet: str


def _run_git(repo_root: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout


def _run_git_ref(repo_root: Path, args: list[str]) -> str:
    return _run_git(repo_root, args).strip()


def _resolve_pre_push_range(repo_root: Path) -> tuple[str, str] | None:
    from_ref = os.getenv("PRE_COMMIT_FROM_REF", "").strip()
    to_ref = os.getenv("PRE_COMMIT_TO_REF", "").strip() or "HEAD"
    if from_ref and from_ref != ZERO_SHA:
        return from_ref, to_ref

    try:
        upstream = _run_git_ref(
            repo_root,
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        )
    except subprocess.CalledProcessError:
        upstream = ""

    if upstream:
        try:
            return _run_git_ref(repo_root, ["merge-base", "HEAD", upstream]), "HEAD"
        except subprocess.CalledProcessError:
            pass
    return None


def _changed_files(repo_root: Path, mode: str, diff_base: str, diff_head: str) -> set[Path]:
    if mode == "all":
        return set()

    if mode == "staged":
        out = _run_git(repo_root, ["diff", "--cached", "--name-only"])
    elif mode == "diff-range":
        out = _run_git(repo_root, ["diff", "--name-only", f"{diff_base}...{diff_head}"])
    else:  # auto
        pre_push_range = _resolve_pre_push_range(repo_root)
        if pre_push_range is not None:
            base, head = pre_push_range
            out = _run_git(repo_root, ["diff", "--name-only", f"{base}...{head}"])
        else:
            staged_out = _run_git(repo_root, ["diff", "--cached", "--name-only"])
            working_out = _run_git(repo_root, ["diff", "--name-only"])
            untracked_out = _run_git(repo_root, ["ls-files", "--others", "--exclude-standard"])
            if staged_out.strip() or working_out.strip() or untracked_out.strip():
                out = "\n".join(
                    chunk
                    for chunk in (
                        staged_out.strip(),
                        working_out.strip(),
                        untracked_out.strip(),
                    )
                    if chunk
                )
            else:
                out = _run_git(repo_root, ["diff", "--name-only", "HEAD~1", "HEAD"])

    changed: set[Path] = set()
    for line in out.splitlines():
        rel = line.strip()
        if not rel:
            continue
        changed.add((repo_root / rel).resolve())
    return changed


def _iter_target_files(repo_root: Path, scan_paths: Iterable[str], changed_files: set[Path]) -> list[Path]:
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
    return [p for p in files if p in changed_files]


def _scan_low_quality_lines(path: Path, source: str) -> list[Finding]:
    findings: list[Finding] = []
    for idx, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        is_log_context = (
            lower.startswith("echo ")
            or lower.startswith("print(")
            or " console." in f" {lower}"
            or lower.startswith("console.")
            or lower.startswith("log_event(")
            or " log_event(" in lower
            or "logger." in lower
            or lower.startswith("raise systemexit(")
            or " raise systemexit(" in lower
        )
        if not is_log_context:
            continue
        hash_idx = line.find("#")
        marker_allowed = hash_idx >= 0 and ALLOW_LOW_QUALITY_MARKER in line[hash_idx + 1 :]
        for phrase in LOW_QUALITY_PATTERNS:
            if phrase in lower:
                if marker_allowed:
                    break
                findings.append(Finding(path, idx, "LOW_QUALITY_LOG_PHRASE", line))
                break
    return findings


def _is_logging_level(node: ast.expr, name: str) -> bool:
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "logging" and node.attr == name


def _get_constant_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _dict_str_keys(node: ast.AST) -> set[str]:
    if not isinstance(node, ast.Dict):
        return set()
    keys: set[str] = set()
    for key_node in node.keys:
        if key_node is None:
            continue
        key_value = _get_constant_str(key_node)
        if key_value is not None:
            keys.add(key_value)
    return keys


def _is_logger_call(node: ast.Call, method: str) -> bool:
    if not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr != method:
        return False
    root = node.func.value
    if isinstance(root, ast.Name):
        return root.id in {"logger", "log"}
    if isinstance(root, ast.Attribute):
        return root.attr == "logger"
    return False


def _event_requires_duration(event_name: str) -> bool:
    lower = event_name.lower()
    return any(lower.endswith(suffix) for suffix in EVENTS_REQUIRE_DURATION_SUFFIXES)


def _scan_structured_error_fields(path: Path, source: str) -> list[Finding]:
    if path.suffix != ".py":
        return []

    findings: list[Finding] = []
    source_lines = source.splitlines()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return findings

    def _has_allow_marker(node: ast.AST) -> bool:
        line_no = max(1, int(getattr(node, "lineno", 1)))
        if line_no <= len(source_lines):
            line = source_lines[line_no - 1]
            hash_idx = line.find("#")
            if hash_idx < 0:
                return False
            return ALLOW_LOW_QUALITY_MARKER in line[hash_idx + 1 :]
        return False

    def _is_low_quality_message(node: ast.expr) -> bool:
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            return False
        msg = node.value.lower()
        return any(phrase in msg for phrase in LOW_QUALITY_PATTERNS)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "log_event":
            continue

        if len(node.args) < 3:
            continue

        event_arg = node.args[2]
        if isinstance(event_arg, ast.Constant) and isinstance(event_arg.value, str):
            event_name = event_arg.value.strip()
            if not event_name:
                findings.append(
                    Finding(
                        path,
                        getattr(node, "lineno", 1),
                        "MISSING_EVENT_NAME",
                        "event must not be empty",
                    )
                )
            elif event_name.lower() in LOW_QUALITY_EVENT_NAMES and not _has_allow_marker(node):
                findings.append(
                    Finding(
                        path,
                        getattr(node, "lineno", 1),
                        "LOW_QUALITY_EVENT_NAME",
                        f"event={event_name}",
                    )
                )

        if len(node.args) >= 4 and _is_low_quality_message(node.args[3]) and not _has_allow_marker(node):
            findings.append(
                Finding(
                    path,
                    getattr(node, "lineno", 1),
                    "LOW_QUALITY_LOG_PHRASE",
                    "log_event message contains low-quality phrase",
                )
            )

        keywords = {kw.arg for kw in node.keywords if kw.arg}
        if isinstance(event_arg, ast.Constant) and isinstance(event_arg.value, str) and _event_requires_duration(event_arg.value.strip()):
            if "duration_ms" not in keywords and "duration_s" not in keywords:
                findings.append(
                    Finding(
                        path,
                        getattr(node, "lineno", 1),
                        "MISSING_DURATION_MS",
                        "key event requires duration_ms (or duration_s for coercion)",
                    )
                )

        level = node.args[1]
        if not (_is_logging_level(level, "ERROR") or _is_logging_level(level, "CRITICAL")):
            continue

        has_explicit_error_fields = "error" in keywords or any(name.startswith("error_") for name in keywords)
        has_exception_context = any(name in keywords for name in EXCEPTION_CONTEXT_FIELDS)
        if not (has_explicit_error_fields or has_exception_context):
            event = node.args[2]
            event_name = event.value if isinstance(event, ast.Constant) and isinstance(event.value, str) else ""
            findings.append(
                Finding(
                    path,
                    getattr(node, "lineno", 1),
                    "MISSING_STRUCTURED_ERROR_FIELDS",
                    f"expected=error/error_* or exception context event={event_name or '<dynamic>'}",
                )
            )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (_is_logger_call(node, "error") or _is_logger_call(node, "exception")):
            continue

        keywords = {kw.arg for kw in node.keywords if kw.arg}
        method = node.func.attr if isinstance(node.func, ast.Attribute) else ""
        extra_keys: set[str] = set()
        fields_keys: set[str] = set()
        has_exception_context = method == "exception"
        for kw in node.keywords:
            if not kw.arg:
                continue
            if kw.arg in EXCEPTION_CONTEXT_FIELDS:
                has_exception_context = True
            if kw.arg == "extra":
                extra_keys |= _dict_str_keys(kw.value)
                continue
            if kw.arg == "fields":
                fields_keys |= _dict_str_keys(kw.value)
                continue
            if kw.arg in REQUIRED_LOG_CONTEXT_FIELDS:
                extra_keys.add(kw.arg)

        fields_nested_keys: set[str] = set()
        if "fields" in extra_keys:
            for kw in node.keywords:
                if kw.arg == "extra" and isinstance(kw.value, ast.Dict):
                    for dict_key, dict_value in zip(kw.value.keys, kw.value.values):
                        if dict_key is None:
                            continue
                        if _get_constant_str(dict_key) == "fields":
                            fields_nested_keys |= _dict_str_keys(dict_value)

        all_context_keys = extra_keys | fields_keys | fields_nested_keys
        missing_context = [name for name in REQUIRED_LOG_CONTEXT_FIELDS if name not in all_context_keys]
        if missing_context:
            findings.append(
                Finding(
                    path,
                    getattr(node, "lineno", 1),
                    "MISSING_LOG_CONTEXT_FIELDS",
                    f"logger.{method} missing={','.join(missing_context)}",
                )
            )

        has_explicit_error_fields = (
            "error" in all_context_keys
            or any(name.startswith("error_") for name in all_context_keys)
            or "error" in keywords
            or any((name or "").startswith("error_") for name in keywords)
        )
        if not (has_exception_context or has_explicit_error_fields):
            findings.append(
                Finding(
                    path,
                    getattr(node, "lineno", 1),
                    "MISSING_STRUCTURED_ERROR_FIELDS",
                    f"logger.{method} requires exception context or error/error_* fields",
                )
            )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="No Logs No Merge gate: block low-quality logs and require structured error fields.")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument(
        "--mode",
        choices=("auto", "all", "staged", "diff-range"),
        default="all",
        help="File selection mode",
    )
    parser.add_argument("--diff-base", default="", help="Diff base (required in diff-range mode)")
    parser.add_argument("--diff-head", default="HEAD", help="Diff head (diff-range mode)")
    parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Path to scan (repeatable). Defaults to key repo paths.",
    )
    args = parser.parse_args()

    if args.mode == "diff-range" and not args.diff_base:
        parser.error("--diff-base is required when --mode=diff-range")

    repo_root = Path(args.root).resolve()
    scan_paths = tuple(args.scan_path) if args.scan_path else DEFAULT_SCAN_PATHS

    changed_files = _changed_files(repo_root, args.mode, args.diff_base, args.diff_head)
    target_files = _iter_target_files(repo_root, scan_paths, changed_files)

    findings: list[Finding] = []
    for path in target_files:
        source = path.read_text(encoding="utf-8", errors="ignore")
        findings.extend(_scan_low_quality_lines(path, source))
        findings.extend(_scan_structured_error_fields(path, source))

    if findings:
        print("❌ no_logs_no_merge_gate: violations detected")
        for item in findings:
            rel = item.path.relative_to(repo_root)
            print(f"- {rel}:{item.line} [{item.rule}] {item.snippet}")
        return 1

    print("✅ no_logs_no_merge_gate: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
