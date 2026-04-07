#!/usr/bin/env python3
"""Ensure pre-commit hooks do not silently skip required tooling."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def _stages_include_pre_commit(stages: list[str] | None) -> bool:
    if not stages:
        # Missing stages means hook defaults include pre-commit.
        return True
    normalized = {str(stage).strip().lower() for stage in stages}
    return "pre-commit" in normalized


def _contains_soft_skip_warn(hook: dict[str, object]) -> bool:
    candidate_texts: list[str] = []
    for field in ("entry", "name"):
        value = hook.get(field)
        if isinstance(value, str):
            candidate_texts.append(value)
    args = hook.get("args")
    if isinstance(args, list):
        for item in args:
            if isinstance(item, str):
                candidate_texts.append(item)
    joined = " ".join(candidate_texts).lower()
    return "warn" in joined and "skip" in joined


def main() -> int:
    cfg = Path(".pre-commit-config.yaml")
    if not cfg.exists():
        print("❌ precommit-strictness: missing .pre-commit-config.yaml")
        return 1

    try:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"❌ precommit-strictness: invalid yaml in {cfg}: {exc}")
        return 1
    if not isinstance(data, dict):
        print("❌ precommit-strictness: invalid top-level config structure")
        return 1

    repos = data.get("repos")
    if not isinstance(repos, list):
        print("❌ precommit-strictness: missing repos list in .pre-commit-config.yaml")
        return 1

    offenders: list[str] = []
    for repo in repos:
        if not isinstance(repo, dict):
            continue
        hooks = repo.get("hooks")
        if not isinstance(hooks, list):
            continue
        repo_name = str(repo.get("repo", "<unknown-repo>"))
        for hook in hooks:
            if not isinstance(hook, dict):
                continue
            stages = hook.get("stages")
            parsed_stages: list[str] | None = None
            if isinstance(stages, list):
                parsed_stages = [str(item) for item in stages]
            elif isinstance(stages, str):
                parsed_stages = [stages]
            if not _stages_include_pre_commit(parsed_stages):
                continue
            if _contains_soft_skip_warn(hook):
                hook_id = str(hook.get("id", "<missing-id>"))
                offenders.append(f"{repo_name}:{hook_id} => {json.dumps(hook, ensure_ascii=False, sort_keys=True)}")

    if offenders:
        print("❌ precommit-strictness: found soft-skip WARN patterns in pre-commit config")
        for offender in offenders:
            print(f"- {offender}")
        return 1

    print("✅ precommit-strictness: no soft-skip WARN patterns found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
