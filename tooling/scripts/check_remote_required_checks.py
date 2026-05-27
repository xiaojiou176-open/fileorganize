#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def _load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid yaml contract: {path}")
    return payload


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False)
    except OSError:
        return None


def _required_contexts(policy: dict) -> list[str]:
    rows = policy.get("required_checks", [])
    if not isinstance(rows, list):
        raise SystemExit("invalid required checks policy: required_checks must be a list")
    contexts: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise SystemExit("invalid required checks policy entry")
        if str(row.get("blocking_level", "")).strip() == "required":
            contexts.append(str(row.get("job_id", "")).strip())
    return sorted(item for item in contexts if item)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate GitHub branch protection required checks stay aligned with repo policy")
    parser.add_argument("--root", default=".")
    parser.add_argument("--required-checks-policy", default="contracts/governance/required_checks_policy.yaml")
    parser.add_argument("--public-readiness-policy", default="contracts/governance/public_readiness_policy.yaml")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    checks_policy = _load_yaml(root / args.required_checks_policy)
    public_policy = _load_yaml(root / args.public_readiness_policy)
    expected_branch = str(checks_policy.get("branch_protection_target", "main")).strip()
    required_contexts = _required_contexts(checks_policy)
    release_policy = public_policy.get("release_mode", {})
    if not isinstance(release_policy, dict):
        raise SystemExit("invalid public readiness policy: release_mode must be an object")

    issues: list[str] = []
    payload: dict[str, object] = {
        "default_branch": expected_branch,
        "required_contexts": required_contexts,
        "observed_contexts": [],
        "repo": None,
        "is_private": None,
        "viewer_permission": None,
        "pvr_enabled": None,
        "platform_query_state": "unknown",
        "issues": issues,
    }

    repo_view = _run(["gh", "repo", "view", "--json", "nameWithOwner,isPrivate,defaultBranchRef,viewerPermission"], root)
    if repo_view is None or repo_view.returncode != 0:
        issues.append("GitHub repo metadata unavailable; cannot verify remote required checks")
    else:
        view = json.loads(repo_view.stdout)
        if not isinstance(view, dict):
            issues.append("invalid gh repo view payload")
        else:
            repo_name = str(view.get("nameWithOwner", "")).strip()
            payload["repo"] = repo_name
            payload["is_private"] = view.get("isPrivate")
            payload["viewer_permission"] = view.get("viewerPermission")
            default_branch_ref = view.get("defaultBranchRef")
            observed_branch = expected_branch
            if isinstance(default_branch_ref, dict):
                observed_branch = str(default_branch_ref.get("name", expected_branch)).strip()
            payload["default_branch"] = observed_branch
            if observed_branch != expected_branch:
                issues.append(f"default branch mismatch: expected {expected_branch}, observed {observed_branch}")
            if bool(release_policy.get("require_public_repo", False)) and payload["is_private"] is True:
                issues.append("release policy requires public repo, but GitHub reports private repository")

            if repo_name:
                viewer_permission = str(payload.get("viewer_permission") or "").upper()
                limited_permission = viewer_permission in {"READ", "TRIAGE", ""}
                pvr_proc = _run(["gh", "api", f"repos/{repo_name}/private-vulnerability-reporting"], root)
                payload["pvr_enabled"] = pvr_proc is not None and pvr_proc.returncode == 0
                if bool(release_policy.get("require_pvr", False)) and not payload["pvr_enabled"]:
                    payload["platform_query_state"] = (
                        "query-blocked-permission-context" if limited_permission else "misconfigured-or-unavailable"
                    )
                    if limited_permission:
                        issues.append(
                            "release policy requires Private Vulnerability Reporting to be queryable/enabled; "
                            f"current viewer permission is {viewer_permission or 'UNKNOWN'}"
                        )
                    else:
                        issues.append("release policy requires Private Vulnerability Reporting to be queryable/enabled")

                protection_proc = _run(["gh", "api", f"repos/{repo_name}/branches/{observed_branch}/protection"], root)
                if protection_proc is None or protection_proc.returncode != 0:
                    payload["platform_query_state"] = (
                        "query-blocked-permission-context" if limited_permission else "misconfigured-or-unavailable"
                    )
                    if limited_permission:
                        issues.append(
                            "branch protection / required checks are not queryable on GitHub "
                            f"with current viewer permission {viewer_permission or 'UNKNOWN'}"
                        )
                    else:
                        issues.append("branch protection / required checks are not queryable on GitHub")
                else:
                    protection = json.loads(protection_proc.stdout)
                    required = protection.get("required_status_checks", {}) if isinstance(protection, dict) else {}
                    observed_contexts: set[str] = set()
                    if isinstance(required, dict):
                        contexts = required.get("contexts", [])
                        checks = required.get("checks", [])
                        if isinstance(contexts, list):
                            observed_contexts.update(str(item) for item in contexts if str(item).strip())
                        if isinstance(checks, list):
                            for item in checks:
                                if isinstance(item, dict):
                                    context = str(item.get("context", "")).strip()
                                    if context:
                                        observed_contexts.add(context)
                    payload["observed_contexts"] = sorted(observed_contexts)
                    missing = sorted(set(required_contexts) - observed_contexts)
                    extra = sorted(observed_contexts - set(required_contexts))
                    if missing:
                        issues.append("missing remote required checks: " + ", ".join(missing))
                    if extra:
                        issues.append("unexpected remote required checks drift: " + ", ".join(extra))
                    if payload["platform_query_state"] == "unknown":
                        payload["platform_query_state"] = "queryable-and-aligned"

    if args.json_out:
        out_path = (root / args.json_out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if issues:
        print("❌ remote-required-checks gate failed")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("remote-required-checks gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
