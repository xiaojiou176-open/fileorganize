#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid public surface contract: {path}")
    return data


def _iter_public_doc_paths(root: Path, contract: dict) -> list[tuple[str, Path]]:
    docs: dict[str, Path] = {}

    for rel in [str(item) for item in contract.get("public_docs", [])]:
        docs[rel] = root / rel

    for raw_pattern in [str(item) for item in contract.get("public_doc_globs", [])]:
        for path in sorted(root.glob(raw_pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            docs.setdefault(rel, path)

    return sorted(docs.items(), key=lambda item: item[0])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate root-facing public surfaces do not advertise internal tooling/scripts entrypoints"
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--contract", default="contracts/governance/public_surface.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    contract = _load_yaml(root / args.contract)
    issues: list[str] = []

    patterns = [re.compile(str(raw)) for raw in contract.get("forbidden_command_patterns", [])]
    for rel, path in _iter_public_doc_paths(root, contract):
        if not path.exists():
            issues.append(f"missing public doc surface: {rel}")
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(pattern.search(line) for pattern in patterns):
                issues.append(f"{rel}:{lineno}: internal tooling/scripts command leaked into public surface")

    package_json = root / "package.json"
    if package_json.exists():
        payload = json.loads(package_json.read_text(encoding="utf-8"))
        scripts = payload.get("scripts", {}) if isinstance(payload, dict) else {}
        if isinstance(scripts, dict):
            forbidden_substrings = [str(item) for item in contract.get("package_json_script_forbidden_substrings", [])]
            for name, command in scripts.items():
                if not isinstance(command, str):
                    continue
                for token in forbidden_substrings:
                    if token in command:
                        issues.append(f"package.json script {name} leaks internal tooling path: {token}")

    if issues:
        sys.stderr.write("root-public-surface gate failed\n")
        for issue in issues:
            sys.stderr.write(f"- {issue}\n")
        return 1

    print("root-public-surface gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
