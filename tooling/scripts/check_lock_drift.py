#!/usr/bin/env python3
"""Fail when dependency lock artifacts drift from pyproject.toml."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

MARKER_RE = re.compile(r"^# source-pyproject-sha256:\s*([0-9a-f]{64})\s*$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_marker(path: Path) -> str | None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            match = MARKER_RE.match(line.strip())
            if match:
                return match.group(1)
    except FileNotFoundError:
        return None
    return None


def _assert_file(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing file: {path}")


def _assert_shell_target(path: Path, expected_line: str, errors: list[str]) -> None:
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except FileNotFoundError:
        errors.append(f"missing file: {path}")
        return
    if expected_line not in lines:
        errors.append(f"{path} must include `{expected_line}`")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    pyproject = root / "pyproject.toml"
    runtime_lock = root / "tooling" / "requirements.lock.txt"
    dev_lock = root / "tooling" / "requirements-dev.lock.txt"
    runtime_shell = root / "tooling" / "requirements.txt"
    dev_shell = root / "tooling" / "requirements-dev.txt"

    errors: list[str] = []
    for file_path in (pyproject, runtime_lock, dev_lock, runtime_shell, dev_shell):
        _assert_file(file_path, errors)
    if errors:
        for error in errors:
            print(f"❌ lock-drift: {error}")
        return 1

    source_hash = _sha256(pyproject)
    for lock_path in (runtime_lock, dev_lock, runtime_shell, dev_shell):
        marker = _read_marker(lock_path)
        if marker is None:
            errors.append(f"{lock_path} missing `# source-pyproject-sha256: ...` marker")
        elif marker != source_hash:
            errors.append(
                f"{lock_path} hash marker mismatch: expected {source_hash}, got {marker}. Run `bash tooling/upstreams/upgrade_deps.sh`."
            )

    _assert_shell_target(runtime_shell, "-r requirements.lock.txt", errors)
    _assert_shell_target(dev_shell, "-r requirements-dev.lock.txt", errors)

    if errors:
        for error in errors:
            print(f"❌ lock-drift: {error}")
        return 1

    print("✅ lock-drift: pyproject and lock artifacts are in sync")
    print(f"source-pyproject-sha256={source_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
