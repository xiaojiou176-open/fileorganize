#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def _load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid snapshot scope policy: {path}")
    return payload


def _required_labels_missing(text: str, required_labels: list[str], allowed_labels: set[str]) -> list[str]:
    missing: list[str] = []
    for label in required_labels:
        if label not in allowed_labels:
            raise SystemExit(f"policy references unknown snapshot scope label: {label}")
        if label not in text:
            missing.append(label)
    return missing


def _latest_plan(repo_root: Path, glob_pattern: str) -> Path | None:
    candidates = sorted(repo_root.glob(glob_pattern), key=lambda path: (path.stat().st_mtime, str(path)))
    return candidates[-1] if candidates else None


def _required_snippets_missing(text: str, required_snippets: list[str]) -> list[str]:
    missing: list[str] = []
    for snippet in required_snippets:
        if snippet not in text:
            missing.append(snippet)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce snapshot-scope labels on time-sensitive docs and active plan surfaces")
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default="contracts/docs/snapshot_scope_policy.yaml")
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    policy = _load_yaml(repo_root / args.policy)
    allowed_labels = {str(item).strip() for item in policy.get("allowed_labels", []) if str(item).strip()}
    if not allowed_labels:
        raise SystemExit("invalid snapshot scope policy: allowed_labels must be non-empty")

    issues: list[str] = []
    for entry in policy.get("required_docs", []):
        if not isinstance(entry, dict):
            issues.append("required_docs contains non-object entry")
            continue
        rel = str(entry.get("path", "")).strip()
        required_labels = [str(item).strip() for item in entry.get("required_labels", []) if str(item).strip()]
        if not rel:
            issues.append("required_docs entry missing path")
            continue
        path = repo_root / rel
        if not path.exists():
            issues.append(f"snapshot-scope target missing: {rel}")
            continue
        missing = _required_labels_missing(path.read_text(encoding="utf-8"), required_labels, allowed_labels)
        if missing:
            issues.append(f"{rel}: missing snapshot scope label(s): {', '.join(missing)}")

    latest_plan_policy = policy.get("latest_plan", {})
    if isinstance(latest_plan_policy, dict):
        latest_plan = _latest_plan(repo_root, str(latest_plan_policy.get("glob", ".agents/Plans/*master-plan*.md")))
        allow_missing = bool(latest_plan_policy.get("allow_missing", False))
        required_labels = [str(item).strip() for item in latest_plan_policy.get("required_labels", []) if str(item).strip()]
        required_snippets = [str(item).strip() for item in latest_plan_policy.get("required_snippets", []) if str(item).strip()]
        if latest_plan is None:
            if not allow_missing:
                issues.append("latest plan missing for snapshot scope enforcement")
        else:
            latest_plan_text = latest_plan.read_text(encoding="utf-8")
            missing = _required_labels_missing(latest_plan_text, required_labels, allowed_labels)
            if missing:
                issues.append(f"{latest_plan.relative_to(repo_root)}: missing snapshot scope label(s): {', '.join(missing)}")
            missing_snippets = _required_snippets_missing(latest_plan_text, required_snippets)
            if missing_snippets:
                issues.append(
                    f"{latest_plan.relative_to(repo_root)}: missing required latest-plan snippet(s): {', '.join(missing_snippets)}"
                )

    if issues:
        print("❌ snapshot_scope_labels: failed")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("✅ snapshot_scope_labels: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
