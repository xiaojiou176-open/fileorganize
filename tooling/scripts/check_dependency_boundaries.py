#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from fnmatch import fnmatch
from pathlib import Path

import yaml

IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z0-9_\.]+)", re.MULTILINE)
TS_IMPORT_RE = re.compile(r"""from\s+["']([^"']+)["']|import\(["']([^"']+)["']\)""")
SKIP_DIRS = {".git", ".runtime-cache", "node_modules", "__pycache__"}


def _load_contract(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid dependency contract: {path}")
    return data


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch(path, pattern) for pattern in patterns)


def _python_imports(path: Path) -> list[str]:
    return [m.group(1) for m in IMPORT_RE.finditer(path.read_text(encoding="utf-8"))]


def _ts_imports(path: Path) -> list[str]:
    out: list[str] = []
    text = path.read_text(encoding="utf-8")
    for m in TS_IMPORT_RE.finditer(text):
        out.append(m.group(1) or m.group(2) or "")
    return [item for item in out if item]


def _iter_repo_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    matches: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(suffixes):
                matches.append(Path(dirpath) / name)
    return matches


def _resolve_ts_repo_import(raw: str, file: Path, root: Path) -> str | None:
    candidate: Path | None = None
    if raw.startswith("@/"):
        candidate = root / "apps" / "webui" / "src" / raw[2:]
    elif raw.startswith("./") or raw.startswith("../"):
        candidate = (file.parent / raw).resolve()
    elif raw.startswith(("apps/", "packages/", "contracts/", "tooling/", "tests/")):
        candidate = root / raw
    else:
        return None

    variants = [
        candidate,
        candidate.with_suffix(".ts"),
        candidate.with_suffix(".tsx"),
        candidate.with_suffix(".js"),
        candidate.with_suffix(".jsx"),
        candidate / "index.ts",
        candidate / "index.tsx",
        candidate / "index.js",
        candidate / "index.jsx",
    ]
    for option in variants:
        if option.exists():
            return option.relative_to(root).as_posix()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dependency boundary contract")
    parser.add_argument("--root", default=".")
    parser.add_argument("--contract", default="contracts/governance/dependency_boundaries.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    contract = _load_contract(root / args.contract)
    issues: list[str] = []

    forbidden_python_roots = tuple(f"{item}." for item in contract.get("forbidden_python_modules", []))
    for layer_name, layer in dict(contract.get("python_layers", {})).items():
        patterns = [str(item) for item in layer.get("paths", [])]
        allowed_modules = tuple(str(item) for item in layer.get("allow_modules", []))
        for file in _iter_repo_files(root, (".py",)):
            rel = file.relative_to(root).as_posix()
            if not _matches(rel, patterns):
                continue
            for imported in _python_imports(file):
                if imported.startswith(forbidden_python_roots):
                    issues.append(f"{rel} imports forbidden python namespace {imported} in layer {layer_name}")
                if imported.startswith("packages.application") and rel.startswith("packages/infrastructure/"):
                    issues.append(f"{rel} imports forbidden application layer dependency {imported}")
                if rel.startswith("packages/domain/") and imported.startswith(
                    ("apps.", "packages.application", "packages.infrastructure", "packages.observability", "tooling.")
                ):
                    issues.append(f"{rel} violates pure domain boundary with import {imported}")
                if imported.startswith(("apps.", "packages.", "tooling.")) and allowed_modules and not imported.startswith(allowed_modules):
                    issues.append(f"{rel} imports {imported} outside allow_modules for {layer_name}")

    for layer_name, layer in dict(contract.get("frontend_layers", {})).items():
        patterns = [str(item) for item in layer.get("paths", [])]
        allowed_roots = tuple(str(item) for item in layer.get("allowed_repo_import_roots", []))
        forbidden_prefixes = tuple(str(item) for item in layer.get("forbidden_import_prefixes", []))
        for file in _iter_repo_files(root, (".ts", ".tsx", ".js", ".jsx")):
            rel = file.relative_to(root).as_posix()
            if not _matches(rel, patterns):
                continue
            for imported in _ts_imports(file):
                normalized = imported.lstrip("./")
                if normalized.startswith(forbidden_prefixes):
                    issues.append(f"{rel} imports forbidden frontend prefix {imported} in layer {layer_name}")
                    continue
                target_rel = _resolve_ts_repo_import(imported, file, root)
                if target_rel is None:
                    continue
                if target_rel.startswith(("apps/api/", "apps/cli/", "packages/", "tooling/", "tests/")):
                    issues.append(f"{rel} imports forbidden repo implementation surface {imported} -> {target_rel}")
                    continue
                if target_rel.startswith("contracts/") and not target_rel.startswith(allowed_roots):
                    issues.append(f"{rel} imports contract surface outside allowlist {imported} -> {target_rel}")

    if issues:
        sys.stderr.write("dependency-boundaries gate failed\n")
        for issue in issues:
            sys.stderr.write(f"- {issue}\n")
        return 1

    print("dependency-boundaries gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
