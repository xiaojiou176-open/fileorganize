#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate truth-route and authority hints across human-authored docs.")
    parser.add_argument("--root", default=".")
    return parser.parse_args()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path(args.root).resolve()
    errors: list[str] = []

    readme = _read(repo_root / "README.md")
    usage = _read(repo_root / "docs" / "usage.md")
    runbook = _read(repo_root / "docs" / "open_source_runbook.md")
    architecture = _read(repo_root / "docs" / "architecture.md")

    if "[docs/usage.md](docs/usage.md)" not in readme:
        errors.append("README.md must route detailed commands to docs/usage.md")
    if "[docs/architecture.md](docs/architecture.md)" not in readme:
        errors.append("README.md must route architecture readers to docs/architecture.md")
    if "[docs/open_source_runbook.md](docs/open_source_runbook.md)" not in readme:
        errors.append("README.md must route public/release/platform boundary to docs/open_source_runbook.md")
    if "Minimal Truth Routes" not in readme:
        errors.append("README.md must expose the minimal truth route section")

    if "[README.md](../README.md)" not in usage:
        errors.append("docs/usage.md must route overview readers back to README.md")
    if "[docs/open_source_runbook.md](./open_source_runbook.md)" not in usage:
        errors.append("docs/usage.md must route public/release/platform boundary to docs/open_source_runbook.md")
    if "detailed operator guide" not in usage:
        errors.append("docs/usage.md must declare itself as the detailed operator guide")

    if "architecture" not in architecture.lower():
        errors.append("docs/architecture.md must remain an architecture-facing document")

    if "This runbook is canonical for public, release, and platform-boundary semantics." not in runbook:
        errors.append("docs/open_source_runbook.md must declare canonical platform/release authority")
    if "Repository docs are not a live platform dashboard." not in runbook:
        errors.append("docs/open_source_runbook.md must keep the live-dashboard warning")

    if errors:
        print("❌ docs_truth_routes: failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print("✅ docs_truth_routes: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
