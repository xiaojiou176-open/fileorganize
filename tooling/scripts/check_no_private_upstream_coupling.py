#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

PY_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z0-9_\.]+)", re.MULTILINE)
TS_IMPORT_RE = re.compile(r"""from\s+["']([^"']+)["']|import\(["']([^"']+)["']\)""")
SKIP_DIRS = {".git", ".runtime-cache", "node_modules", "__pycache__"}


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid private coupling policy: {path}")
    return data


def _iter_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            if filename.endswith(suffixes):
                out.append(Path(dirpath) / filename)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Block coupling to private upstream implementation surfaces")
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default="contracts/upstreams/private_coupling_policy.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy = _load_yaml(root / args.policy)
    issues: list[str] = []

    local_python_prefixes = tuple(str(item) for item in policy.get("local_python_prefixes", []))
    forbidden_python_segments = tuple(str(item) for item in policy.get("forbidden_python_segments", []))
    for rel_root in [str(item) for item in policy.get("python_scan_roots", [])]:
        scan_root = root / rel_root
        if not scan_root.exists():
            continue
        for path in _iter_files(scan_root, (".py",)):
            rel = path.relative_to(root).as_posix()
            text = path.read_text(encoding="utf-8")
            for match in PY_IMPORT_RE.finditer(text):
                imported = match.group(1)
                if imported.startswith(local_python_prefixes):
                    continue
                if any(segment in imported for segment in forbidden_python_segments):
                    issues.append(f"{rel}: private upstream python import {imported}")

    forbidden_frontend_segments = tuple(str(item) for item in policy.get("forbidden_frontend_segments", []))
    for rel_root in [str(item) for item in policy.get("frontend_scan_roots", [])]:
        scan_root = root / rel_root
        if not scan_root.exists():
            continue
        for path in _iter_files(scan_root, (".ts", ".tsx", ".js", ".jsx")):
            rel = path.relative_to(root).as_posix()
            text = path.read_text(encoding="utf-8")
            for match in TS_IMPORT_RE.finditer(text):
                imported = match.group(1) or match.group(2) or ""
                if not imported or imported.startswith(("./", "../", "@/")):
                    continue
                if imported.startswith(("apps/", "packages/", "contracts/", "tooling/", "tests/")):
                    continue
                if any(segment in imported for segment in forbidden_frontend_segments):
                    issues.append(f"{rel}: private upstream frontend import {imported}")

    compiled_text_patterns = [re.compile(str(pattern)) for pattern in policy.get("forbidden_text_patterns", [])]
    for rel_root in [str(item) for item in policy.get("text_scan_roots", [])]:
        scan_root = root / rel_root
        if not scan_root.exists():
            continue
        for path in _iter_files(scan_root, (".py", ".sh", ".yml", ".yaml", ".ts", ".tsx", ".js", ".jsx")):
            rel = path.relative_to(root).as_posix()
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if any(pattern.search(line) for pattern in compiled_text_patterns):
                    issues.append(f"{rel}:{lineno}: private upstream filesystem/text coupling")

    if issues:
        sys.stderr.write("no-private-upstream-coupling gate failed\n")
        for issue in issues:
            sys.stderr.write(f"- {issue}\n")
        return 1

    print("no-private-upstream-coupling gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
