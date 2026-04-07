#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

EXPECTED_TRACKED_POLICY = "must-remain-untracked"


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"invalid yaml contract: {path}")
    return data


def _run_git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def _tracked_paths(root: Path, entry: str) -> list[str]:
    proc = _run_git(root, ["ls-files", "--cached", "--", entry])
    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or "unknown git error"
        raise RuntimeError(f"unable to read git tracked reality for {entry}: {message}")
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _local_only_entries(allowlist: dict) -> set[str]:
    return {str(item) for item in allowlist.get("local_only_entries", [])}


def _tracked_enforcement_entries(allowlist: dict) -> list[str]:
    tracking = allowlist.get("local_only_tracking", {})
    if not isinstance(tracking, dict):
        raise SystemExit("invalid local_only_tracking contract")
    entries = tracking.get("entries", [])
    if not isinstance(entries, list) or not entries:
        raise SystemExit("local_only_tracking.entries must be a non-empty list")
    return [str(item) for item in entries]


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-close when local-only root entries leak into the git tracked surface")
    parser.add_argument("--root", default=".")
    parser.add_argument("--allowlist", default="contracts/governance/root_allowlist.yaml")
    parser.add_argument("--contract", default="contracts/governance/root_change_control.yaml")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    allowlist = _load_yaml(root / args.allowlist)
    change_control = _load_yaml(root / args.contract)

    local_only_entries = _local_only_entries(allowlist)
    tracking = allowlist.get("local_only_tracking", {})
    if not isinstance(tracking, dict):
        raise SystemExit("invalid local_only_tracking contract")

    mode = str(tracking.get("mode", "")).strip()
    enforcement_target = str(tracking.get("enforcement_target", "")).strip()
    require_policy = bool(tracking.get("require_change_control_tracked_policy", False))
    enforced_entries = _tracked_enforcement_entries(allowlist)

    issues: list[str] = []

    if mode != "fail-close":
        issues.append("local_only_tracking.mode must be fail-close")
    if enforcement_target != "git-tracked-surface":
        issues.append("local_only_tracking.enforcement_target must be git-tracked-surface")
    for entry in enforced_entries:
        if entry not in local_only_entries:
            issues.append(f"local_only_tracking entry is not declared local-only: {entry}")

    entries = change_control.get("entries", {})
    if not isinstance(entries, dict):
        raise SystemExit(f"invalid entries mapping: {args.contract}")

    git_probe = _run_git(root, ["rev-parse", "--show-toplevel"])
    git_available = git_probe.returncode == 0

    for entry in enforced_entries:
        meta = entries.get(entry)
        if not isinstance(meta, dict):
            issues.append(f"missing change-control metadata for local-only entry: {entry}")
            continue
        if str(meta.get("change_class", "")).strip() != "local-only":
            issues.append(f"local-only entry must keep change_class=local-only: {entry}")
        if require_policy and str(meta.get("tracked_policy", "")).strip() != EXPECTED_TRACKED_POLICY:
            issues.append(f"missing tracked_policy metadata for local-only entry: {entry}")
        if require_policy and not str(meta.get("tracked_policy_reason", "")).strip():
            issues.append(f"missing tracked_policy_reason for local-only entry: {entry}")
        if git_available:
            try:
                tracked_paths = _tracked_paths(root, entry)
            except RuntimeError as exc:
                issues.append(str(exc))
                continue
            if tracked_paths:
                issues.append(f"local-only entry leaked into tracked surface: {entry} -> {', '.join(tracked_paths)}")

    if issues:
        sys.stderr.write("local-only-tracking gate failed\n")
        for issue in issues:
            sys.stderr.write(f"- {issue}\n")
        return 1

    print("local-only-tracking gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
