#!/usr/bin/env python3
"""Verify required checks matrix is fully rendered from workflow + policy SSOT."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from docs_render_lib import REPO_ROOT, render_required_checks_matrix, validate_required_checks


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matrix",
        default=str(REPO_ROOT / "docs" / "required_checks_matrix.md"),
        help="Path to required checks matrix markdown file.",
    )
    parser.add_argument(
        "--workflow",
        default=str(REPO_ROOT / ".github" / "workflows" / "ci.yml"),
        help="Path to GitHub Actions workflow YAML file.",
    )
    parser.add_argument(
        "--require-merge-group",
        action="store_true",
        help="Fail if the workflow does not declare merge_group trigger.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    matrix_path = Path(args.matrix).resolve()

    if not matrix_path.exists():
        print(f"❌ matrix file not found: {matrix_path}")
        return 2

    errors = validate_required_checks(REPO_ROOT)
    if errors:
        print("❌ required checks policy invalid")
        for error in errors:
            print(f"- {error}")
        return 1

    expected = render_required_checks_matrix(REPO_ROOT)
    current = matrix_path.read_text(encoding="utf-8")
    if current != expected:
        print("❌ required checks matrix is stale")
        print(f"- stale: {matrix_path.relative_to(REPO_ROOT)}")
        print("fix: python3 tooling/scripts/render_docs.py")
        return 1

    print("✅ required checks matrix is rendered and aligned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
