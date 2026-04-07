#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate run bundle contract exists")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    schema = root / "contracts/runtime/run_bundle.schema.json"
    if not schema.exists():
        sys.stderr.write("run-bundle-contract gate failed\n- missing contracts/runtime/run_bundle.schema.json\n")
        return 1
    print("run-bundle-contract gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
