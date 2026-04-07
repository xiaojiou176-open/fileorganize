#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from fnmatch import fnmatch
from pathlib import Path

import yaml  # type: ignore[import-untyped]

PY_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z0-9_\.]+)", re.MULTILINE)
TS_IMPORT_RE = re.compile(r"""from\s+["']([^"']+)["']|import\(["']([^"']+)["']\)""")
SKIP_DIRS = {".git", ".runtime-cache", "__pycache__", "node_modules"}
MANAGED_PYTHON_ROOTS = ("apps/", "packages/", "tooling/scripts/", "tests/")
SKIP_PYTHON_FILES = {"apps/__init__.py", "packages/__init__.py"}


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid yaml: {path}")
    return data


def _matches(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch(rel, pattern) for pattern in patterns)


def _iter_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            if filename.endswith(suffixes):
                out.append(Path(dirpath) / filename)
    return out


def _layer_name_for_path(rel: str, layers: dict[str, dict]) -> str | None:
    for layer_name, layer in layers.items():
        if _matches(rel, [str(item) for item in layer.get("paths", [])]):
            return layer_name
    return None


def _python_module_name(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    if rel.endswith("/__init__.py"):
        rel = rel[: -len("/__init__.py")]
    else:
        rel = rel[: -len(".py")]
    return rel.replace("/", ".")


def _build_python_module_map(root: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for file in _iter_files(root, (".py",)):
        rel = file.relative_to(root).as_posix()
        if not rel.startswith(MANAGED_PYTHON_ROOTS):
            continue
        mapping[_python_module_name(file, root)] = rel
    return mapping


def _resolve_python_import(imported: str, module_map: dict[str, str]) -> str | None:
    candidate = imported
    while candidate:
        if candidate in module_map:
            return module_map[candidate]
        if "." not in candidate:
            break
        candidate = candidate.rsplit(".", 1)[0]
    return None


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
    parser = argparse.ArgumentParser(description="Validate module graph contract against current repo graph")
    parser.add_argument("--root", default=".")
    parser.add_argument("--contract", default="contracts/governance/module_graph.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    contract = _load_yaml(root / args.contract)
    layers = {str(name): dict(value) for name, value in dict(contract.get("layers", {})).items()}
    issues: list[str] = []
    module_map = _build_python_module_map(root)

    for layer_name, layer in layers.items():
        for pattern in [str(item) for item in layer.get("may_import_from", [])]:
            if pattern.endswith("/**"):
                prefix = pattern[:-3]
                if not (root / prefix).exists():
                    issues.append(f"layer {layer_name} references missing contract path: {pattern}")
            elif not (root / pattern).exists():
                issues.append(f"layer {layer_name} references missing contract path: {pattern}")

    for file in _iter_files(root, (".py",)):
        rel = file.relative_to(root).as_posix()
        if not rel.startswith(MANAGED_PYTHON_ROOTS):
            continue
        if rel in SKIP_PYTHON_FILES:
            continue
        python_layer_name: str | None = _layer_name_for_path(rel, layers)
        if python_layer_name is None:
            issues.append(f"unowned python file: {rel}")
            continue
        allowed_patterns = [str(item) for item in layers[python_layer_name].get("may_import_from", [])]
        allowed_patterns.extend([str(item) for item in layers[python_layer_name].get("paths", [])])
        text = file.read_text(encoding="utf-8")
        for match in PY_IMPORT_RE.finditer(text):
            imported = match.group(1)
            if imported.startswith(("tests.", "webui.", "pipeline.", "packages.core.pipeline")):
                issues.append(f"{rel} imports forbidden legacy prefix {imported}")
                continue
            if rel == "tooling/scripts/generate_api_contract.py" and imported == "apps.api.web_api":
                continue
            if not imported.startswith(("apps.", "packages.", "tooling.", "tests.")):
                continue
            target_rel = _resolve_python_import(imported, module_map)
            if target_rel is None:
                issues.append(f"{rel} imports unresolved managed module {imported}")
                continue
            if not _matches(target_rel, allowed_patterns):
                issues.append(f"{rel} imports {imported} -> {target_rel} outside allowed module graph")

    for file in _iter_files(root, (".ts", ".tsx", ".js", ".jsx")):
        rel = file.relative_to(root).as_posix()
        frontend_layer_name: str | None = _layer_name_for_path(rel, layers)
        if frontend_layer_name is None:
            if rel.startswith("apps/webui/src/"):
                issues.append(f"unowned frontend file: {rel}")
            continue
        allowed_patterns = [str(item) for item in layers[frontend_layer_name].get("may_import_from", [])]
        allowed_patterns.extend([str(item) for item in layers[frontend_layer_name].get("paths", [])])
        text = file.read_text(encoding="utf-8")
        for match in TS_IMPORT_RE.finditer(text):
            imported = match.group(1) or match.group(2) or ""
            if not imported:
                continue
            target_rel = _resolve_ts_repo_import(imported, file, root)
            if target_rel is None:
                continue
            if not _matches(target_rel, allowed_patterns):
                issues.append(f"{rel} imports {imported} -> {target_rel} outside allowed module graph")

    if issues:
        sys.stderr.write("module-graph gate failed\n")
        for issue in issues:
            sys.stderr.write(f"- {issue}\n")
        return 1
    print("module-graph gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
