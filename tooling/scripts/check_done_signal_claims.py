#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def _load_contract(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid done signal contract: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate repository-facing done signal claims stay aligned with governance policy")
    parser.add_argument("--root", default=".")
    parser.add_argument("--contract", default="contracts/governance/done_signal_policy.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    contract = _load_contract(root / args.contract)
    issues: list[str] = []

    claim_surfaces = contract.get("claim_surfaces", [])
    if not isinstance(claim_surfaces, list):
        raise SystemExit("invalid done signal contract: claim_surfaces must be a list")

    for entry in claim_surfaces:
        if not isinstance(entry, dict):
            issues.append("done signal contract contains non-object claim surface entry")
            continue
        rel = str(entry.get("path", "")).strip()
        required_snippets = entry.get("required_snippets", [])
        if not rel:
            issues.append("done signal contract claim surface is missing path")
            continue
        if not isinstance(required_snippets, list) or not all(isinstance(item, str) for item in required_snippets):
            issues.append(f"{rel}: required_snippets must be a list of strings")
            continue

        path = root / rel
        if not path.exists():
            issues.append(f"missing done signal claim surface: {rel}")
            continue

        content = path.read_text(encoding="utf-8")
        for snippet in required_snippets:
            if snippet not in content:
                issues.append(f"{rel}: missing required done signal snippet: {snippet}")

    if issues:
        sys.stderr.write("done-signal-claims gate failed\n")
        for issue in issues:
            sys.stderr.write(f"- {issue}\n")
        return 1

    print("done-signal-claims gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
