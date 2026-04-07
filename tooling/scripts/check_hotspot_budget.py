#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import os
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def _load_contract(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid hotspot budget contract: {path}")
    return payload


def _line_count(path: Path) -> int:
    return path.read_text(encoding="utf-8").count("\n") + 1


def _imports_shim(module_name: str, tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module_name:
                    return True
        elif isinstance(node, ast.ImportFrom):
            from_module = node.module or ""
            if from_module == module_name or from_module.startswith(module_name + "."):
                return True
            if from_module == "packages.application":
                if any(alias.name == "apply_changes" for alias in node.names):
                    return True
    return False


def _collect_python_files(root: Path) -> list[Path]:
    try:
        return [path for path in root.rglob("*.py") if ".runtime-cache" not in path.parts and ".agents" not in path.parts]
    except FileNotFoundError:
        python_files: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            dirnames[:] = [name for name in dirnames if name not in {".runtime-cache", ".agents", ".git", "node_modules", ".venv"}]
            for filename in filenames:
                if filename.endswith(".py"):
                    python_files.append(Path(dirpath) / filename)
        return python_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate hotspot line budgets and shim import boundaries")
    parser.add_argument("--root", default=".")
    parser.add_argument("--contract", default="contracts/governance/hotspot_budget.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    contract = _load_contract(root / args.contract)
    issues: list[str] = []

    hotspots = contract.get("hotspots", [])
    if not isinstance(hotspots, list):
        raise SystemExit("invalid hotspot budget contract: hotspots must be a list")
    for entry in hotspots:
        if not isinstance(entry, dict):
            raise SystemExit("invalid hotspot budget contract: hotspot entry must be an object")
        rel = str(entry.get("path", "")).strip()
        max_lines = int(entry.get("max_lines", 0))
        path = root / rel
        if not rel or max_lines <= 0:
            raise SystemExit(f"invalid hotspot budget entry: {entry!r}")
        if not path.exists():
            issues.append(f"missing hotspot file: {rel}")
            continue
        lines = _line_count(path)
        if lines > max_lines:
            issues.append(f"{rel}: line budget exceeded ({lines} > {max_lines})")

    shim_guards = contract.get("shim_guards", [])
    if not isinstance(shim_guards, list):
        raise SystemExit("invalid hotspot budget contract: shim_guards must be a list")
    python_files = _collect_python_files(root)
    for guard in shim_guards:
        if not isinstance(guard, dict):
            raise SystemExit("invalid hotspot budget contract: shim guard must be an object")
        shim_path = str(guard.get("shim_path", "")).strip()
        module_name = str(guard.get("module_name", "")).strip()
        allowed_importers = guard.get("allowed_importers", [])
        allowed_prefixes = guard.get("allowed_importer_prefixes", [])
        if not shim_path or not module_name or not isinstance(allowed_importers, list) or not isinstance(allowed_prefixes, list):
            raise SystemExit(f"invalid hotspot budget shim guard: {guard!r}")
        shim_abs = root / shim_path
        for py_file in python_files:
            if py_file == shim_abs:
                continue
            rel = py_file.relative_to(root).as_posix()
            if rel in {str(item) for item in allowed_importers}:
                continue
            if any(rel.startswith(prefix) for prefix in allowed_prefixes):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=rel)
            except SyntaxError as exc:
                issues.append(f"{rel}: unable to parse while checking shim imports: {exc}")
                continue
            if _imports_shim(module_name, tree):
                issues.append(f"{rel}: forbidden non-test import of shim module {module_name}")

    if issues:
        print("❌ hotspot-budget gate failed")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("hotspot-budget gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
