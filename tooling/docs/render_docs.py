#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render docs outputs and generated fragments from SSOT files.")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--check", action="store_true", help="Check whether rendered outputs are current without writing")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.root).resolve()
    script_dir = Path(__file__).resolve().parent
    scripts_dir = script_dir.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    build_render_outputs = importlib.import_module("docs_render_lib").build_render_outputs
    outputs, _ = build_render_outputs(repo_root)
    mismatches: list[str] = []
    for rel_path, rendered in outputs.items():
        target = repo_root / rel_path
        current = target.read_text(encoding="utf-8") if target.exists() else None
        if current != rendered:
            mismatches.append(rel_path)
            if not args.check:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(rendered, encoding="utf-8")
    if args.check and mismatches:
        print("❌ render_docs: stale outputs detected")
        for rel_path in mismatches:
            print(f"- {rel_path}")
        print("fix: python3 tooling/docs/render_docs.py")
        return 1
    action = "checked" if args.check else "rendered"
    print(f"✅ render_docs: {action}")
    print(f"outputs={len(outputs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
