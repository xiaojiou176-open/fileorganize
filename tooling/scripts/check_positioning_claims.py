#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def _load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid claims contract: {path}")
    return payload


def _iter_claim_surfaces(contract: dict, label: str) -> list[tuple[str, list[str]]]:
    claim_surfaces = contract.get("claim_surfaces", [])
    if not isinstance(claim_surfaces, list):
        raise SystemExit(f"invalid {label} contract: claim_surfaces must be a list")
    rows: list[tuple[str, list[str]]] = []
    for entry in claim_surfaces:
        if not isinstance(entry, dict):
            raise SystemExit(f"invalid {label} contract: claim surface must be an object")
        rel = str(entry.get("path", "")).strip()
        snippets = entry.get("required_snippets", [])
        if not rel or not isinstance(snippets, list) or not all(isinstance(item, str) for item in snippets):
            raise SystemExit(f"invalid {label} contract claim surface: {entry!r}")
        rows.append((rel, [str(item) for item in snippets]))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate public positioning and claims stay aligned with governance contracts")
    parser.add_argument("--root", default=".")
    parser.add_argument("--positioning-contract", default="contracts/governance/project_positioning.yaml")
    parser.add_argument("--claims-contract", default="contracts/governance/public_claims_policy.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    positioning = _load_yaml(root / args.positioning_contract)
    claims = _load_yaml(root / args.claims_contract)
    issues: list[str] = []

    for rel, snippets in _iter_claim_surfaces(positioning, "project_positioning"):
        path = root / rel
        if not path.exists():
            issues.append(f"missing positioning claim surface: {rel}")
            continue
        content = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in content:
                issues.append(f"{rel}: missing required positioning snippet: {snippet}")

    forbidden_phrases = claims.get("forbidden_phrases", [])
    if not isinstance(forbidden_phrases, list) or not all(isinstance(item, str) for item in forbidden_phrases):
        raise SystemExit("invalid public claims contract: forbidden_phrases must be a list of strings")

    for rel, snippets in _iter_claim_surfaces(claims, "public_claims"):
        path = root / rel
        if not path.exists():
            issues.append(f"missing public claims surface: {rel}")
            continue
        content = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in content:
                issues.append(f"{rel}: missing required public-claims snippet: {snippet}")
        for phrase in forbidden_phrases:
            if phrase in content:
                issues.append(f"{rel}: forbidden stale/overclaim phrase present: {phrase}")

    if issues:
        print("❌ positioning-claims gate failed")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("positioning-claims gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
