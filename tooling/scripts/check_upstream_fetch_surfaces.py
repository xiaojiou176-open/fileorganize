#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RAW_DOWNLOAD_PATTERN = re.compile(r"\b(curl|wget)\b")
PYTHON_URLLIB_PATTERN = re.compile(r"urllib\.request\.urlopen")


def _scan_file(path: Path, root: Path, issues: list[str]) -> None:
    if path.name in {"check_org_shared_runners.py", "check_runner_inventory.py", "check_upstream_fetch_surfaces.py"}:
        return
    text = path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), 1):
        if RAW_DOWNLOAD_PATTERN.search(line):
            if "fetch_upstream_artifact.py" in line:
                continue
            issues.append(f"{path.relative_to(root)}:{lineno}: unmanaged download surface")
        if PYTHON_URLLIB_PATTERN.search(line) and path.name != "fetch_upstream_artifact.py":
            issues.append(f"{path.relative_to(root)}:{lineno}: unmanaged python download surface")


def main() -> int:
    parser = argparse.ArgumentParser(description="Block unmanaged upstream downloads")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    issues: list[str] = []
    for path in sorted((root / ".github" / "workflows").glob("*.yml")):
        _scan_file(path, root, issues)
    for path in sorted((root / "tooling" / "scripts").glob("*.py")):
        _scan_file(path, root, issues)
    if issues:
        sys.stderr.write("upstream-fetch-surfaces gate failed\n")
        for issue in issues:
            sys.stderr.write(f"- {issue}\n")
        return 1
    print("upstream-fetch-surfaces gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
