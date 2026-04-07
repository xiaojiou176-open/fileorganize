#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from docs_render_lib import load_docs_nav_registry

TRACKED_SUFFIXES = {".md", ".json"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate docs scope boundaries using docs_nav_registry.")
    parser.add_argument("--root", default=".", help="Repository root")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.root).resolve()
    registry = load_docs_nav_registry(repo_root)
    docs = list(registry.get("docs", []))
    registered = {str(item["path"]): item for item in docs}
    errors: list[str] = []

    for rel_path, item in registered.items():
        path = repo_root / rel_path
        if not path.exists():
            errors.append(f"registered doc missing: {rel_path}")
            continue
        scope = str(item.get("scope", ""))
        layer = str(item.get("layer", ""))
        if scope == "generated" and not any(token in rel_path for token in ("/reference/", "/_generated/")):
            errors.append(f"generated scope must live under reference/_generated: {rel_path}")
        if layer == "archive" and "/_archive/" not in rel_path:
            errors.append(f"archive layer must live under docs/_archive/: {rel_path}")
        if scope == "soft" and "/_archive/" not in rel_path and "/docs/" in rel_path:
            errors.append(f"soft-scope docs must be isolated archive docs: {rel_path}")

    for path in sorted((repo_root / "docs").rglob("*")):
        if not path.is_file() or path.suffix not in TRACKED_SUFFIXES:
            continue
        rel_path = path.relative_to(repo_root).as_posix()
        if rel_path not in registered:
            errors.append(f"unregistered docs asset under docs: {rel_path}")

    legacy_paths = [
        "docs/code_review.md",
        "docs/我和ChatGPT的完整对话.md",
        "docs/env_contract_baseline.json",
        "docs/gate_history_baseline.json",
    ]
    for rel_path in legacy_paths:
        if (repo_root / rel_path).exists():
            errors.append(f"legacy docs path must be moved out of strict docs tree: {rel_path}")

    if errors:
        print("❌ docs_scope: invalid docs scope boundary")
        for error in errors:
            print(f"- {error}")
        return 1

    print("✅ docs_scope: passed")
    print(f"registered_docs={len(registered)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
