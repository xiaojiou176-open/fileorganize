#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _config_path(repo_root: Path) -> Path:
    modern = repo_root / "contracts" / "governance" / "change_detection_scope.json"
    legacy = repo_root / "脚本" / "config" / "change_detection_scope.json"
    if modern.exists():
        return modern
    return legacy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve whether changed files should trigger heavy CI paths.")
    parser.add_argument("--changed-file-list", required=True, help="Path to newline-separated changed files list")
    parser.add_argument("--print-mode", choices=("shell", "plain"), default="shell")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = json.loads(_config_path(REPO_ROOT).read_text(encoding="utf-8"))
    patterns = [str(item) for item in config.get("heavy_globs", [])]
    changed_file = Path(args.changed_file_list)
    changed = [line.strip().replace("\\", "/") for line in changed_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    run_heavy = any(any(fnmatch.fnmatch(path, pattern) or Path(path).match(pattern) for pattern in patterns) for path in changed)
    if args.print_mode == "plain":
        print("true" if run_heavy else "false")
    else:
        print(f"run-heavy={'true' if run_heavy else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
