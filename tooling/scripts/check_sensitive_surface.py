#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

FORBIDDEN_TRACKED_EXTENSIONS = {
    ".db",
    ".dmp",
    ".dump",
    ".har",
    ".key",
    ".log",
    ".pcap",
    ".pem",
    ".sqlite",
}
PERSONAL_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@(?:gmail\.com|outlook\.com|hotmail\.com|qq\.com|icloud\.com|163\.com|126\.com|yahoo\.com)\b",
    re.IGNORECASE,
)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[-. ]?)?(?:\(?[2-9]\d{2}\)?[-. ])\d{3}[-. ]\d{4}(?!\d)")
AUTHORIZATION_HEADER_DUMP_RE = re.compile(r"(?i)\bauthorization\s*:\s*(?:bearer|basic|token)\s+[A-Za-z0-9._~+/=-]{12,}")
SET_COOKIE_HEADER_DUMP_RE = re.compile(r"(?i)\bset-cookie\s*:\s*[A-Za-z0-9._-]{1,64}=[^;\s]{8,}")
BEARER_VALUE_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{16,}")


def _unix_private_path_pattern(root_segment: str) -> re.Pattern[str]:
    return re.compile(rf"(?P<full>/{root_segment}/(?P<user>[A-Za-z0-9._-]+)/)")


def _windows_private_path_pattern() -> re.Pattern[str]:
    return re.compile(r"(?P<full>[A-Za-z]:\\\\Users\\\\(?P<user>[A-Za-z0-9._-]+)\\\\)", re.IGNORECASE)


ABSOLUTE_PATH_PATTERNS = (
    ("ABSOLUTE_PRIVATE_PATH", _unix_private_path_pattern("Users")),
    ("ABSOLUTE_PRIVATE_PATH", _unix_private_path_pattern("home")),
    ("ABSOLUTE_PRIVATE_PATH", _windows_private_path_pattern()),
)
ZERO_SHA = "0" * 40


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int | None
    rule: str
    snippet: str


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )


def _run_git_stdout(repo_root: Path, args: list[str]) -> str:
    proc = _run_git(repo_root, args)
    if proc.returncode != 0:
        return ""
    return proc.stdout


def _git_available(repo_root: Path) -> bool:
    return _run_git(repo_root, ["rev-parse", "--show-toplevel"]).returncode == 0


def _resolve_pre_push_range(repo_root: Path) -> tuple[str, str] | None:
    from_ref = os.getenv("PRE_COMMIT_FROM_REF", "").strip()
    to_ref = os.getenv("PRE_COMMIT_TO_REF", "").strip() or "HEAD"
    if from_ref and from_ref != ZERO_SHA:
        return from_ref, to_ref

    upstream = _run_git_stdout(
        repo_root,
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
    ).strip()
    if upstream:
        base = _run_git_stdout(repo_root, ["merge-base", "HEAD", upstream]).strip()
        if base:
            return base, "HEAD"
    return None


def _tracked_files(repo_root: Path) -> list[Path]:
    proc = _run_git(repo_root, ["ls-files", "-z"])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "unable to read tracked files")
    files: list[Path] = []
    for entry in proc.stdout.split("\0"):
        rel = entry.strip()
        if not rel:
            continue
        files.append((repo_root / rel).resolve())
    return files


def _changed_files(repo_root: Path, mode: str, diff_base: str, diff_head: str) -> set[Path]:
    if mode == "all":
        return set()

    if mode == "staged":
        out = _run_git_stdout(repo_root, ["diff", "--cached", "--name-only"])
    elif mode == "diff-range":
        out = _run_git_stdout(repo_root, ["diff", "--name-only", f"{diff_base}...{diff_head}"])
    else:
        pre_push_range = _resolve_pre_push_range(repo_root)
        if pre_push_range is not None:
            base, head = pre_push_range
            out = _run_git_stdout(repo_root, ["diff", "--name-only", f"{base}...{head}"])
        else:
            staged_out = _run_git_stdout(repo_root, ["diff", "--cached", "--name-only"])
            working_out = _run_git_stdout(repo_root, ["diff", "--name-only"])
            untracked_out = _run_git_stdout(repo_root, ["ls-files", "--others", "--exclude-standard"])
            if staged_out.strip() or working_out.strip() or untracked_out.strip():
                out = "\n".join(chunk for chunk in (staged_out.strip(), working_out.strip(), untracked_out.strip()) if chunk)
            else:
                out = _run_git_stdout(repo_root, ["diff", "--name-only", "HEAD~1", "HEAD"])

    changed: set[Path] = set()
    for line in out.splitlines():
        rel = line.strip()
        if not rel:
            continue
        changed.add((repo_root / rel).resolve())
    return changed


def _looks_binary(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:4096]
    except OSError:
        return True
    return b"\0" in sample


def _iter_candidate_files(repo_root: Path, mode: str, diff_base: str, diff_head: str) -> list[Path]:
    if not _git_available(repo_root):
        if mode != "all":
            raise RuntimeError("sensitive-surface gate requires git for non-all modes")
        files: list[Path] = []
        for path in sorted(repo_root.rglob("*")):
            if not path.is_file():
                continue
            if any(part in {".git", ".venv", ".venv-matrix", ".runtime-cache", "node_modules"} for part in path.parts):
                continue
            files.append(path.resolve())
        return files

    changed = _changed_files(repo_root, mode, diff_base, diff_head)
    files = _tracked_files(repo_root)
    if not changed:
        return [path for path in files if path.exists()]
    return [path for path in files if path.exists() and path in changed]


def _shorten(text: str) -> str:
    trimmed = " ".join(text.strip().split())
    if len(trimmed) <= 180:
        return trimmed
    return trimmed[:177] + "..."


def _scan_path_text(path: Path, source: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_no, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.rstrip("\n")
        for rule, pattern in ABSOLUTE_PATH_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            findings.append(Finding(path, line_no, rule, _shorten(match.group("full"))))
            break
        email_match = PERSONAL_EMAIL_RE.search(line)
        if email_match:
            findings.append(Finding(path, line_no, "PERSONAL_EMAIL", _shorten(email_match.group(0))))
        phone_match = PHONE_RE.search(line)
        if phone_match:
            findings.append(Finding(path, line_no, "PHONE_NUMBER", _shorten(phone_match.group(0))))
        authorization_match = AUTHORIZATION_HEADER_DUMP_RE.search(line)
        if authorization_match:
            findings.append(Finding(path, line_no, "SENSITIVE_HEADER_DUMP", _shorten(authorization_match.group(0))))
        cookie_match = SET_COOKIE_HEADER_DUMP_RE.search(line)
        if cookie_match:
            findings.append(Finding(path, line_no, "SENSITIVE_HEADER_DUMP", _shorten(cookie_match.group(0))))
        bearer_match = BEARER_VALUE_RE.search(line)
        if bearer_match:
            findings.append(Finding(path, line_no, "SENSITIVE_BEARER_DUMP", _shorten(bearer_match.group(0))))
    return findings


def _scan_filename(repo_root: Path, path: Path) -> list[Finding]:
    rel = path.relative_to(repo_root).as_posix()
    if rel == ".env.example":
        return []
    suffix = path.suffix.lower()
    if suffix in FORBIDDEN_TRACKED_EXTENSIONS:
        return [Finding(path, None, "FORBIDDEN_TRACKED_ARTIFACT", rel)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-close when tracked surfaces leak private paths, personal info, or unsafe artifacts")
    parser.add_argument("--root", default=".")
    parser.add_argument("--mode", choices=("all", "auto", "staged", "diff-range"), default="all")
    parser.add_argument("--diff-base", default="")
    parser.add_argument("--diff-head", default="HEAD")
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    try:
        files = _iter_candidate_files(repo_root, args.mode, args.diff_base, args.diff_head)
    except RuntimeError as exc:
        print(f"❌ sensitive-surface gate failed\n- {exc}", file=sys.stderr)
        return 1

    findings: list[Finding] = []
    for path in files:
        findings.extend(_scan_filename(repo_root, path))
        if _looks_binary(path):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        findings.extend(_scan_path_text(path, source))

    if findings:
        print("❌ sensitive-surface gate failed")
        for item in findings:
            rel = item.path.relative_to(repo_root).as_posix()
            location = f"{rel}:{item.line}" if item.line is not None else rel
            print(f"- {item.rule} {location}: {item.snippet}")
        return 1

    print("sensitive-surface gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
