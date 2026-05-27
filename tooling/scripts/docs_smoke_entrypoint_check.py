#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

OUTPUT_SNIPPET_LIMIT = 800


def _coerce_text(payload: bytes | str) -> str:
    if isinstance(payload, bytes):
        return payload.decode("utf-8", errors="ignore")
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate that a package smoke entrypoint handles --help cleanly.")
    parser.add_argument("--entrypoint-path", required=True, help="Absolute path to the installed entrypoint binary.")
    parser.add_argument("--entrypoint-name", required=True, help="Human-readable entrypoint name for diagnostics.")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=5.0,
        help="Max seconds to wait for `<entrypoint> --help` before failing.",
    )
    return parser.parse_args()


def _print_stream(label: str, payload: str) -> None:
    trimmed = payload.strip()
    if not trimmed:
        return
    print(f"{label}:", file=sys.stderr)
    print(trimmed[-OUTPUT_SNIPPET_LIMIT:], file=sys.stderr)


def main() -> int:
    args = _parse_args()
    entrypoint_path = Path(args.entrypoint_path)
    if not entrypoint_path.exists():
        print(
            f"❌ docs_smoke: missing entrypoint binary: {args.entrypoint_name} -> {entrypoint_path}",
            file=sys.stderr,
        )
        return 1

    try:
        proc = subprocess.run(
            [str(entrypoint_path), "--help"],
            capture_output=True,
            text=True,
            timeout=args.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        print(
            f"❌ docs_smoke: entrypoint timed out after {args.timeout_seconds:g}s: {args.entrypoint_name}",
            file=sys.stderr,
        )
        _print_stream("stdout", _coerce_text(exc.stdout or ""))
        _print_stream("stderr", _coerce_text(exc.stderr or ""))
        return 1

    if proc.returncode != 0:
        print(
            f"❌ docs_smoke: entrypoint exited non-zero: {args.entrypoint_name} (rc={proc.returncode})",
            file=sys.stderr,
        )
        _print_stream("stdout", proc.stdout)
        _print_stream("stderr", proc.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
