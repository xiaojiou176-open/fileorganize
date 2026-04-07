#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a governed release evidence summary")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default=".runtime-cache/logs/release-evidence/summary.json")
    return parser.parse_args()


def _extract_version(pyproject_text: str) -> str:
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject_text, flags=re.MULTILINE)
    if not match:
        raise SystemExit("version not found in pyproject.toml")
    return match.group(1)


def _current_tag(repo_root: Path) -> str:
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    return f"v{_extract_version(pyproject)}"


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _git_rev_parse(repo_root: Path, ref: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", ref],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None


def _commits_match(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    left_norm = left.strip().lower()
    right_norm = right.strip().lower()
    return left_norm == right_norm or left_norm.startswith(right_norm) or right_norm.startswith(left_norm)


def _gh_release_view(repo_root: Path, tag_name: str) -> tuple[dict[str, object] | None, str | None]:
    try:
        proc = subprocess.run(
            [
                "gh",
                "release",
                "view",
                tag_name,
                "--json",
                "tagName,isDraft,isPrerelease,url,targetCommitish,publishedAt",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None, "gh CLI unavailable"
    if proc.returncode != 0:
        reason = proc.stderr.strip() or proc.stdout.strip() or "unknown gh release view failure"
        return None, reason
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, "invalid gh release payload"
    return (payload if isinstance(payload, dict) else None), None


def _load_release_verify_summary(repo_root: Path, tag_name: str) -> dict[str, object] | None:
    summary = _read_json(repo_root / ".runtime-cache" / "logs" / "release-publish" / "summary.json")
    if not isinstance(summary, dict):
        return None
    if str(summary.get("tag_name", "")).strip() != tag_name:
        return None
    return summary


def _build_remote_release_boundary(repo_root: Path, tag_name: str) -> dict[str, object]:
    release_payload, lookup_reason = _gh_release_view(repo_root, tag_name)
    verify_summary = _load_release_verify_summary(repo_root, tag_name)
    head_commit = _git_rev_parse(repo_root, "HEAD")

    boundary: dict[str, object] = {
        "tag_name": tag_name,
        "status": "pending_remote_workflow_run",
        "required_actions": [
            "materialize and push the release tag on GitHub",
            "run .github/workflows/release.yml in draft or publish mode",
            "verify remote release assets and checksums with verify_release_publish.sh",
        ],
    }

    if verify_summary is not None:
        boundary["verification_summary"] = {
            "path": ".runtime-cache/logs/release-publish/summary.json",
            "status": verify_summary.get("status"),
            "publish_mode": verify_summary.get("publish_mode"),
            "generated_at": verify_summary.get("generated_at"),
        }

    if release_payload is None:
        if lookup_reason and "release not found" in lookup_reason.lower():
            boundary["status"] = "pending_remote_workflow_run"
            boundary["lookup_status"] = "release_not_found"
        else:
            boundary["status"] = "github_release_lookup_unavailable"
            boundary["lookup_status"] = "lookup_failed"
            boundary["lookup_reason"] = lookup_reason or "unknown lookup failure"
        return boundary

    is_draft = bool(release_payload.get("isDraft"))
    is_prerelease = bool(release_payload.get("isPrerelease"))
    boundary["remote_release"] = {
        "tag_name": release_payload.get("tagName"),
        "url": release_payload.get("url"),
        "target_commitish": release_payload.get("targetCommitish"),
        "is_draft": is_draft,
        "is_prerelease": is_prerelease,
        "published_at": release_payload.get("publishedAt"),
    }
    if head_commit is not None:
        boundary["current_head_commit"] = head_commit

    remote_target = str(release_payload.get("targetCommitish", "")).strip() or None
    if remote_target and not _commits_match(head_commit, remote_target):
        boundary["status"] = "remote_release_not_current_head"
        boundary["required_actions"] = [
            "bump the source version or create a new release tag from the current HEAD instead of reusing an older published release",
            "rerun npm run release:truth after source-version and tag alignment",
            "verify remote release assets and checksums with verify_release_publish.sh once the correct current-head tag exists",
        ]
        return boundary

    if verify_summary is not None and str(verify_summary.get("status", "")).strip() == "pass":
        boundary["status"] = "published_release_verified" if not is_draft else "draft_release_verified"
        boundary["required_actions"] = [
            "review the verified release assets, checksums, and provenance outputs",
            "promote the draft only after the release notes and asset set are final",
        ]
        return boundary

    if is_draft:
        boundary["status"] = "draft_exists_not_published"
        boundary["required_actions"] = [
            "refresh local release evidence so it reflects the existing remote draft reality",
            "review the draft asset set, SBOM files, and provenance outputs",
            "run publish mode and post-publish verification when ready",
        ]
        return boundary

    boundary["status"] = "published_release_exists"
    boundary["required_actions"] = [
        "run verify_release_publish.sh for the current tag if no fresh verification summary exists",
        "review the published release assets, checksums, and provenance outputs",
    ]
    return boundary


def _build_current_head_release_truth(remote_release_boundary: dict[str, object]) -> dict[str, object]:
    status = str(remote_release_boundary.get("status", "pending_remote_workflow_run")).strip() or "pending_remote_workflow_run"
    required_actions = remote_release_boundary.get("required_actions", [])
    if not isinstance(required_actions, list):
        required_actions = []

    statement_map = {
        "pending_remote_workflow_run": (
            "Current-head release closure is not established yet. The release workflow still needs to run for this tag."
        ),
        "github_release_lookup_unavailable": (
            "Current-head release truth could not be confirmed from GitHub. Treat the release state as unknown until the lookup succeeds."
        ),
        "remote_release_not_current_head": (
            "A remote release exists for this version line, but it targets an older commit instead of the current HEAD."
        ),
        "draft_exists_not_published": (
            "A remote draft exists for the current head, but verified published closure is not established yet."
        ),
        "draft_release_verified": (
            "The current draft release asset set was freshly verified, but draft verification is still not the same as published closure."
        ),
        "published_release_exists": (
            "A published release exists, but there is no fresh verification receipt proving the current remote asset set."
        ),
        "published_release_verified": (
            "The current-head release is published and freshly verified. This is the only status that proves verified published closure."
        ),
    }

    return {
        "operator_entrypoint": "npm run release:truth",
        "summary_path": ".runtime-cache/logs/release-evidence/summary.json",
        "status": status,
        "verified_published_closure": status == "published_release_verified",
        "closure_rule": "Only `published_release_verified` counts as verified published closure.",
        "operator_read_order": [
            "current_head_release_truth.status",
            "current_head_release_truth.safe_operator_statement",
            "current_head_release_truth.next_required_actions",
            "remote_release_boundary.remote_release",
            "remote_release_boundary.verification_summary",
        ],
        "non_closure_statuses": [
            "pending_remote_workflow_run",
            "github_release_lookup_unavailable",
            "remote_release_not_current_head",
            "draft_exists_not_published",
            "draft_release_verified",
            "published_release_exists",
        ],
        "safe_operator_statement": statement_map.get(
            status,
            "Current-head release truth is unknown; do not claim closure until a fresh verified status exists.",
        ),
        "next_required_actions": required_actions,
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(args.root).resolve()
    output = (repo_root / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    tag_name = _current_tag(repo_root)
    remote_release_boundary = _build_remote_release_boundary(repo_root, tag_name)
    required_actions = remote_release_boundary.get("required_actions", [])
    if not isinstance(required_actions, list):
        required_actions = []

    payload = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "target_release": {
            "tag_name": tag_name,
            "version_source": "pyproject.toml",
        },
        "release_draft": ".runtime-cache/logs/release-draft.md",
        "ci_image_provenance": {
            "status": "wired",
            "artifact_hint": ".runtime-cache/attestations/provenance-summary.json",
        },
        "release_asset_provenance": {
            "status": "workflow_wired",
            "reason": (
                "GitHub Release asset provenance is wired via .github/workflows/release.yml "
                "but still requires a workflow run to produce fresh attestations"
            ),
        },
        "sbom": {
            "status": "workflow_wired",
            "reason": (
                "Python and Node SBOM generation are wired into the release workflow "
                "but still require a workflow run to produce fresh assets"
            ),
        },
        "release_stage_policy": {
            "status": "workflow_wired",
            "allowed_modes": ["bundle-only", "draft", "publish"],
            "tag_policy": "vMAJOR.MINOR.PATCH or vMAJOR.MINOR.PATCH-(alpha|beta|rc).N",
        },
        "post_publish_verification": {
            "status": "workflow_wired",
            "verify_entrypoint": "bash tooling/ci/verify_release_publish.sh <tag> <mode>",
        },
        "repo_side_release_reality": {
            "status": "verifiable_locally",
            "fresh_local_proofs": [
                "bash tooling/ci/validate_release_tag.sh <tag> <mode>",
                "bash tooling/ci/build_release_bundle.sh <tag> <output-dir>",
                "bash tooling/gates/public_readiness_gate.sh release",
                "bash tooling/gates/platform_alignment_gate.sh",
            ],
        },
        "current_head_release_truth": _build_current_head_release_truth(remote_release_boundary),
        "remote_release_boundary": remote_release_boundary,
        "hardening_gap_vs_ci": {
            "status": "explicitly_accounted",
            "items": [
                (
                    "release workflow stays single-lane because draft/publish side effects "
                    "should not run twice across hosted and fallback lanes"
                ),
                (
                    "CI dual-lane merge gating remains the canonical merge-time trust boundary; "
                    "release workflow focuses on post-merge delivery reality"
                ),
            ],
        },
        "next_required_actions": required_actions,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"release evidence written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
