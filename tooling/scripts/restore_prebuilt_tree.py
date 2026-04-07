#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path


def _clear_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)


def _copy_symlink(src: Path, dst: Path) -> None:
    target = os.readlink(src)
    if dst.exists() or dst.is_symlink():
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink(missing_ok=True)
    os.symlink(target, dst)


def _sync_tree(src: Path, dst: Path) -> None:
    for child in src.iterdir():
        target = dst / child.name
        if child.is_symlink():
            _copy_symlink(child, target)
            continue
        if child.is_dir():
            if target.exists() and (not target.is_dir() or target.is_symlink()):
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                else:
                    target.unlink(missing_ok=True)
            shutil.copytree(child, target, symlinks=True, dirs_exist_ok=True)
            continue
        if target.exists() and target.is_dir():
            shutil.rmtree(target)
        elif target.exists() or target.is_symlink():
            target.unlink(missing_ok=True)
        shutil.copy2(child, target, follow_symlinks=False)


def restore_prebuilt_tree(src: Path, dst: Path) -> None:
    if not src.is_dir():
        raise SystemExit(f"restore_prebuilt_tree: source directory not found: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    _clear_dir(dst)

    temp_parent = dst.parent
    temp_prefix = f".{dst.name}.restore-"
    temp_dir_path = Path(tempfile.mkdtemp(prefix=temp_prefix, dir=temp_parent))
    try:
        _sync_tree(src, temp_dir_path)
        _sync_tree(temp_dir_path, dst)
    finally:
        shutil.rmtree(temp_dir_path, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a prebuilt tree into an existing target directory")
    parser.add_argument("--src", required=True)
    parser.add_argument("--dst", required=True)
    args = parser.parse_args()

    restore_prebuilt_tree(Path(args.src).expanduser().resolve(), Path(args.dst).expanduser().resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
