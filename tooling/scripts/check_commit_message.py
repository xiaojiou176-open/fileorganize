#!/usr/bin/env python3
"""Validate commit messages against Conventional Commits."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ZERO_SHA = "0" * 40
CURRENT_REPO_ROOT = REPO_ROOT
BASELINE_PATH = REPO_ROOT / "脚本" / "config" / "governance-baselines" / "gate_history_baseline.json"

ALLOWED_TYPES = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
)

CONVENTIONAL_PATTERN = re.compile(
    rf"^(?:fixup!\s+|squash!\s+)?(?:{'|'.join(ALLOWED_TYPES)})"
    r"(?:\([a-z0-9][a-z0-9._/-]*\))?"
    r"(?:!)?:\s.+$"
)


def _normalize_message(raw: str) -> str:
    for line in raw.splitlines():
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        return candidate
    return ""


def _is_valid_message(subject: str) -> tuple[bool, str | None]:
    if not subject:
        return False, "empty commit subject"
    if subject.startswith("Merge "):
        return True, None
    if subject.startswith("Revert "):
        return True, None
    if not CONVENTIONAL_PATTERN.fullmatch(subject):
        allowed = ", ".join(ALLOWED_TYPES)
        return (
            False,
            f"must match Conventional Commits, e.g. feat(scope): message (allowed types: {allowed})",
        )
    return True, None


def _check_message_file(path: Path) -> int:
    subject = _normalize_message(path.read_text(encoding="utf-8", errors="ignore"))
    ok, error = _is_valid_message(subject)
    if ok:
        print(f"✅ commit-msg gate: passed ({subject})")
        return 0
    print("❌ commit-msg gate: failed")
    print(f"- file: {path}")
    print(f"- subject: {subject or '<empty>'}")
    print(f"- reason: {error}")
    return 1


def _collect_commits(from_ref: str, to_ref: str) -> list[tuple[str, str]]:
    proc = subprocess.run(
        [
            "git",
            "log",
            "--no-merges",
            "--format=%H%x01%s",
            f"{from_ref}..{to_ref}",
        ],
        cwd=CURRENT_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    commits: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        if "\x01" not in line:
            continue
        sha, subject = line.split("\x01", maxsplit=1)
        commits.append((sha.strip(), subject.strip()))
    return commits


def _load_legacy_commit_allowlist() -> set[str]:
    if not BASELINE_PATH.exists():
        return set()
    try:
        data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return set()
    values = data.get("legacy_non_conventional_commits", [])
    if not isinstance(values, list):
        return set()
    return {str(item).strip() for item in values if str(item).strip()}


def _run_git_ref(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=CURRENT_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _first_ref_line(raw: str) -> str:
    for line in raw.splitlines():
        candidate = line.strip()
        if candidate:
            return candidate
    return ""


def _resolve_default_from_ref() -> str:
    try:
        upstream = _run_git_ref(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
    except subprocess.CalledProcessError:
        upstream = ""

    if upstream:
        try:
            return _run_git_ref(["merge-base", "HEAD", upstream])
        except subprocess.CalledProcessError:
            pass

    for candidate in ("refs/remotes/origin/HEAD", "origin/main", "origin/master"):
        try:
            remote_ref = _run_git_ref(["symbolic-ref", "--short", candidate]) if candidate == "refs/remotes/origin/HEAD" else candidate
            if remote_ref:
                return _run_git_ref(["merge-base", "HEAD", remote_ref])
        except subprocess.CalledProcessError:
            continue

    roots_raw = _run_git_ref(["rev-list", "--max-parents=0", "HEAD"])
    first_root = _first_ref_line(roots_raw)
    if first_root:
        return first_root
    return _run_git_ref(["rev-parse", "HEAD"])


def _check_commit_range(from_ref: str, to_ref: str, require_non_empty_range: bool = False) -> int:
    commits = _collect_commits(from_ref, to_ref)
    if not commits:
        if require_non_empty_range:
            print("❌ commit-msg gate: failed")
            print(f"- no commits found in range: {from_ref}...{to_ref}")
            print("- reason: empty range is blocked in strict mode (--require-non-empty-range)")
            return 1
        print(f"⚠️ commit-msg gate: no commits to check in range {from_ref}...{to_ref} (compat mode pass)")
        print("hint: enable --require-non-empty-range to fail on empty commit ranges")
        return 0

    legacy_allowlist = _load_legacy_commit_allowlist()
    failures: list[str] = []
    for sha, subject in commits:
        if sha in legacy_allowlist:
            continue
        ok, error = _is_valid_message(subject)
        if not ok:
            failures.append(f"{sha[:12]} {subject} -> {error}")

    if failures:
        print("❌ commit-msg gate: failed")
        for failure in failures:
            print(f"- {failure}")
        return 1

    checked = len([sha for sha, _ in commits if sha not in legacy_allowlist])
    skipped = len(commits) - checked
    print(
        f"✅ commit-msg gate: passed ({checked} commits checked in {from_ref}...{to_ref}"
        f"{', legacy_skipped=' + str(skipped) if skipped else ''})"
    )
    return 0


def _resolve_pre_push_refs() -> tuple[str, str]:
    from_ref = os.getenv("PRE_COMMIT_FROM_REF", "").strip()
    to_ref = os.getenv("PRE_COMMIT_TO_REF", "").strip() or "HEAD"
    if from_ref and from_ref != ZERO_SHA:
        return _first_ref_line(from_ref), to_ref
    return _resolve_default_from_ref(), to_ref


def main(argv: list[str]) -> int:
    global CURRENT_REPO_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Git repository root (default: project root).",
    )
    parser.add_argument(
        "--commit-msg-file",
        help="Path to commit message file (for commit-msg hook).",
    )
    parser.add_argument(
        "--from-ref",
        help="Git ref start (for CI range checks).",
    )
    parser.add_argument(
        "--pre-push-auto",
        action="store_true",
        help="Resolve range from PRE_COMMIT_FROM_REF/PRE_COMMIT_TO_REF (for pre-push hook).",
    )
    parser.add_argument(
        "--to-ref",
        default="HEAD",
        help="Git ref end (default: HEAD).",
    )
    parser.add_argument(
        "--require-non-empty-range",
        action="store_true",
        help="Fail when commit range resolves to zero commits (strict mode).",
    )
    args = parser.parse_args(argv)
    CURRENT_REPO_ROOT = Path(args.repo_root).resolve()

    if args.commit_msg_file:
        return _check_message_file(Path(args.commit_msg_file).resolve())

    if args.from_ref:
        try:
            return _check_commit_range(
                args.from_ref,
                args.to_ref,
                require_non_empty_range=args.require_non_empty_range,
            )
        except subprocess.CalledProcessError as exc:
            print(f"❌ commit-msg gate: git command failed: {exc}", file=sys.stderr)
            return 2

    if args.pre_push_auto:
        from_ref, to_ref = _resolve_pre_push_refs()
        try:
            return _check_commit_range(
                from_ref,
                to_ref,
                require_non_empty_range=args.require_non_empty_range,
            )
        except subprocess.CalledProcessError as exc:
            print(f"❌ commit-msg gate: git command failed: {exc}", file=sys.stderr)
            return 2

    parser.error("Provide --commit-msg-file, --from-ref, or --pre-push-auto")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
