#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _run(repo_root: Path, command: list[str]) -> None:
    env = dict(os.environ)
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    proc = subprocess.run(command, cwd=str(repo_root), env=env, text=True, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prove the repo can cold-start from cleaned runtime state and still rebuild its governed outputs"
    )
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    _run(repo_root, ["bash", "tooling/runtime/verify_cold_start.sh"])
    _run(repo_root, [sys.executable, "tooling/scripts/check_root_layout.py", "--root", str(repo_root)])
    _run(repo_root, [sys.executable, "tooling/scripts/check_root_clean_after_mainflows.py", "--root", str(repo_root)])
    _run(repo_root, [sys.executable, "tooling/scripts/check_repo_runtime_residue.py", "--root", str(repo_root)])
    _run(repo_root, [sys.executable, "tooling/scripts/check_runtime_layout.py", "--root", str(repo_root)])
    _run(repo_root, [sys.executable, "tooling/scripts/check_runtime_budget.py", "--root", str(repo_root)])
    print("cold-start-rebuild gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
