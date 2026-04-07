#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from docs_render_lib import GENERATED_BLOCK_PATTERN, load_docs_nav_registry, load_yaml

RULES_PATH = Path(__file__).resolve().parents[2] / "contracts" / "docs" / "docs_manual_fact_rules.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Block overview docs from hand-maintaining machine fact inventories.")
    parser.add_argument("--root", default=".", help="Repository root")
    return parser.parse_args()


def strip_generated_blocks(text: str) -> str:
    return GENERATED_BLOCK_PATTERN.sub("", text)


def load_manual_fact_rules(repo_root: Path) -> tuple[set[str], dict[str, list[str]]]:
    modern = repo_root / "contracts" / "docs" / "docs_manual_fact_rules.yaml"
    legacy = repo_root / "脚本" / "config" / "docs_manual_fact_rules.yaml"
    payload = load_yaml(modern if modern.exists() else legacy)
    target_layers = {str(item).strip() for item in payload.get("target_layers", []) if str(item).strip()}
    rules: dict[str, list[str]] = {}
    for rule_name, raw_rule in dict(payload.get("rules", {})).items():
        if not isinstance(raw_rule, dict):
            continue
        patterns = [str(item) for item in raw_rule.get("patterns", []) if str(item)]
        rules[str(rule_name)] = patterns
    return target_layers, rules


def main() -> int:
    args = parse_args()
    repo_root = Path(args.root).resolve()
    registry = load_docs_nav_registry(repo_root)
    target_layers, rules = load_manual_fact_rules(repo_root)
    errors: list[str] = []
    checked_docs = 0
    for item in registry.get("docs", []):
        if not isinstance(item, dict):
            continue
        rel_path = str(item.get("path", ""))
        if not rel_path:
            continue
        if str(item.get("scope", "")) != "strict":
            continue
        layer = str(item.get("layer", ""))
        if layer not in target_layers and not bool(item.get("manual_fact_enforced", False)):
            continue
        path = repo_root / rel_path
        if not path.exists():
            errors.append(f"manual-facts target missing: {rel_path}")
            continue
        checked_docs += 1
        manual_text = strip_generated_blocks(path.read_text(encoding="utf-8"))
        exemptions = {str(rule_name) for rule_name in item.get("manual_fact_rule_exemptions", []) if str(rule_name)}
        for rule_name, patterns in rules.items():
            if rule_name in exemptions:
                continue
            for needle in patterns:
                if needle in manual_text:
                    errors.append(f"{rel_path}: {rule_name} -> {needle}")
    if errors:
        print("❌ docs_manual_facts: overview docs still contain banned hand-maintained fact blocks")
        for error in errors:
            print(f"- {error}")
        return 1
    print("✅ docs_manual_facts: passed")
    print(f"checked_docs={checked_docs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
