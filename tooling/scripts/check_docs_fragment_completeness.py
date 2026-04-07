#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from docs_render_lib import load_docs_nav_registry, load_docs_render_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate that docs_nav_registry fully declares every fragment render block.")
    parser.add_argument("--root", default=".", help="Repository root")
    return parser.parse_args()


def _collect_fragment_blocks(manifest: dict) -> tuple[dict[str, set[str]], list[str]]:
    outputs: dict[str, set[str]] = {}
    errors: list[str] = []
    for entry in manifest.get("renders", []):
        if not isinstance(entry, dict) or str(entry.get("kind", "")).strip() != "fragment":
            continue
        render_id = str(entry.get("id", "<unknown>")).strip()
        output_path = str(entry.get("output_path", "")).strip()
        block_id = str(entry.get("block_id", "")).strip()
        if not output_path:
            errors.append(f"{render_id}: fragment render missing output_path")
            continue
        if not block_id:
            errors.append(f"{render_id}: fragment render missing block_id")
            continue
        outputs.setdefault(output_path, set())
        if block_id in outputs[output_path]:
            errors.append(f"{output_path}: duplicate fragment block_id declared in render manifest: {block_id}")
            continue
        outputs[output_path].add(block_id)
    return outputs, errors


def main() -> int:
    args = parse_args()
    repo_root = Path(args.root).resolve()
    manifest = load_docs_render_manifest(repo_root)
    registry = load_docs_nav_registry(repo_root)

    fragment_blocks_by_output, errors = _collect_fragment_blocks(manifest)
    docs_entries = list(registry.get("docs", []))
    registered = {
        str(item.get("path", "")).strip(): item for item in docs_entries if isinstance(item, dict) and str(item.get("path", "")).strip()
    }

    for output_path, expected_blocks in sorted(fragment_blocks_by_output.items()):
        entry = registered.get(output_path)
        if entry is None:
            errors.append(f"{output_path}: fragment render output missing from docs_nav_registry")
            continue
        generated_blocks = entry.get("generated_blocks", [])
        if not isinstance(generated_blocks, list) or not all(isinstance(item, str) for item in generated_blocks):
            errors.append(f"{output_path}: generated_blocks must be a list of strings")
            continue
        declared_blocks = {item.strip() for item in generated_blocks if item.strip()}
        for block_id in sorted(expected_blocks - declared_blocks):
            errors.append(f"{output_path}: missing generated_blocks entry for fragment block `{block_id}`")

    for output_path, entry in sorted(registered.items()):
        generated_blocks = entry.get("generated_blocks")
        if generated_blocks is None:
            continue
        if not isinstance(generated_blocks, list) or not all(isinstance(item, str) for item in generated_blocks):
            errors.append(f"{output_path}: generated_blocks must be a list of strings")
            continue
        manifest_blocks = fragment_blocks_by_output.get(output_path, set())
        for block_id in sorted({item.strip() for item in generated_blocks if item.strip()}):
            if block_id not in manifest_blocks:
                errors.append(f"{output_path}: generated_blocks declares unknown fragment block `{block_id}`")

    if errors:
        print("❌ docs_fragment_completeness: invalid fragment registry coverage")
        for error in errors:
            print(f"- {error}")
        return 1

    print("✅ docs_fragment_completeness: passed")
    print(f"fragment_outputs={len(fragment_blocks_by_output)}")
    print(f"fragment_blocks={sum(len(blocks) for blocks in fragment_blocks_by_output.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
