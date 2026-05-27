#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from docs_render_lib import load_docs_render_manifest, sha256_file, sha256_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate docs render_state source/output hashes against current SSOT files.")
    parser.add_argument("--root", default=".", help="Repository root")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.root).resolve()
    manifest = load_docs_render_manifest(repo_root)
    render_state_path = repo_root / str(manifest["render_state_path"])
    if not render_state_path.exists():
        print(f"❌ docs_ssot_hash: missing render_state: {render_state_path.relative_to(repo_root)}")
        return 1
    state = json.loads(render_state_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for item in state.get("renders", []):
        output_path = str(item["output_path"])
        current_output = repo_root / output_path
        if not current_output.exists():
            errors.append(f"missing output: {output_path}")
        else:
            current_output_hash = sha256_text(current_output.read_text(encoding="utf-8"))
            if current_output_hash != item.get("output_hash"):
                errors.append(f"output hash drift: {output_path}")
        for rel_path, expected_hash in dict(item.get("source_hashes", {})).items():
            source = repo_root / rel_path
            if not source.exists():
                errors.append(f"missing source: {rel_path}")
                continue
            current_hash = sha256_file(source)
            if current_hash != expected_hash:
                errors.append(f"source hash drift: {rel_path} -> {output_path}")
    if errors:
        print("❌ docs_ssot_hash: render_state no longer matches current SSOT/output hashes")
        for error in errors:
            print(f"- {error}")
        print("fix: python3 tooling/scripts/render_docs.py")
        return 1
    print("✅ docs_ssot_hash: passed")
    print(f"tracked_outputs={len(state.get('renders', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
