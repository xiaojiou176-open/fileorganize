#!/usr/bin/env python3
"""Fail commit when render sources/outputs drift out of sync."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from docs_render_lib import build_render_outputs, load_docs_render_manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
ZERO_SHA = "0" * 40
GLOBAL_RENDER_SOURCES = {
    "contracts/docs/docs_render_manifest.yaml",
    "contracts/docs/docs_nav_registry.yaml",
    "tooling/scripts/docs_render_lib.py",
    "tooling/scripts/render_docs.py",
}


def _normalize(paths: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw in paths:
        item = raw.strip()
        if not item:
            continue
        # pre-commit can pass absolute paths in some environments.
        try:
            rel = Path(item).resolve().relative_to(REPO_ROOT)
            normalized.append(rel.as_posix())
        except Exception:
            normalized.append(item.replace("\\", "/"))
    return normalized


def _run_git_name_only(args: list[str]) -> list[str]:
    proc = subprocess.run(
        ["git", "-c", "core.quotePath=off", *args, "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in proc.stdout.split("\0") if line]


def _staged_files() -> list[str]:
    return _run_git_name_only(["diff", "--cached", "--name-only"])


def _working_tree_files() -> list[str]:
    return _run_git_name_only(["diff", "--name-only"])


def _untracked_files() -> list[str]:
    return _run_git_name_only(["ls-files", "--others", "--exclude-standard"])


def _last_commit_files() -> list[str]:
    return _run_git_name_only(["diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"])


def _range_files(diff_base: str, diff_head: str) -> list[str]:
    # Use merge-base aware diff range for stable PR checks.
    return _run_git_name_only(["diff", "--name-only", f"{diff_base}...{diff_head}"])


def _run_git_ref(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _ref_exists(ref: str) -> bool:
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}^{{commit}}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def _resolve_pre_push_range() -> tuple[str, str] | None:
    from_ref = os.getenv("PRE_COMMIT_FROM_REF", "").strip()
    to_ref = os.getenv("PRE_COMMIT_TO_REF", "").strip() or "HEAD"

    if from_ref and from_ref != ZERO_SHA:
        if not (_ref_exists(from_ref) and _ref_exists(to_ref)):
            return None
        return from_ref, to_ref

    try:
        upstream = _run_git_ref(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
    except subprocess.CalledProcessError:
        upstream = ""

    if upstream:
        try:
            base = _run_git_ref(["merge-base", "HEAD", upstream])
            return base, "HEAD"
        except subprocess.CalledProcessError:
            pass

    return None


def _merge_changed_files(*groups: list[str]) -> list[str]:
    merged: set[str] = set()
    for group in groups:
        merged.update(group)
    return sorted(merged)


def _changed_files_from_mode(mode: str, diff_base: str | None, diff_head: str) -> list[str]:
    if mode == "staged":
        return _staged_files()
    if mode == "working-tree":
        return _working_tree_files()
    if mode == "last-commit":
        return _last_commit_files()
    if mode == "diff-range":
        if not diff_base:
            raise ValueError("--diff-base is required when --mode=diff-range")
        return _range_files(diff_base, diff_head)
    if mode == "auto":
        pre_push_range = _resolve_pre_push_range()
        staged = _staged_files()
        working_tree = _working_tree_files()
        untracked = _untracked_files()
        if pre_push_range is not None:
            base, head = pre_push_range
            range_files = _range_files(base, head)
            if staged or working_tree or untracked:
                return _merge_changed_files(range_files, staged, working_tree, untracked)
            return range_files
        if staged or working_tree or untracked:
            return _merge_changed_files(staged, working_tree, untracked)
        return _last_commit_files()
    raise ValueError(f"Unsupported mode: {mode}")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Block render drift: generated docs must move with their declared sources.")
    parser.add_argument(
        "--mode",
        choices=("staged", "working-tree", "last-commit", "diff-range", "auto"),
        default="staged",
        help="How to collect changed files (default: staged).",
    )
    parser.add_argument(
        "--diff-base",
        help="Base ref for --mode=diff-range (e.g. origin/main or commit SHA).",
    )
    parser.add_argument(
        "--diff-head",
        default="HEAD",
        help="Head ref for --mode=diff-range (default: HEAD).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print changed-file set before evaluating.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional explicit file paths. When provided, git diff discovery is skipped.",
    )
    return parser.parse_args(argv)


def _discover_changed_files(args: argparse.Namespace) -> list[str]:
    if args.paths:
        return _normalize(args.paths)
    proc = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or proc.stdout.strip() != "true":
        print("doc-drift: not a git work tree, skip")
        return []
    return _normalize(_changed_files_from_mode(args.mode, args.diff_base, args.diff_head))


def _print_change_list(header: str, items: list[str]) -> None:
    print(header)
    for item in items:
        print(f"- {item}")


def _stale_render_outputs() -> list[str]:
    expected, _ = build_render_outputs(REPO_ROOT)
    stale: list[str] = []
    for rel_path, rendered in expected.items():
        target = REPO_ROOT / rel_path
        current = target.read_text(encoding="utf-8") if target.exists() else None
        if current != rendered:
            stale.append(rel_path)
    return stale


def _current_render_outputs() -> dict[str, str]:
    expected, _ = build_render_outputs(REPO_ROOT)
    return expected


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    try:
        changed = _discover_changed_files(args)
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(f"doc-drift: failed to discover changed files: {exc}", file=sys.stderr)
        return 2

    if not changed:
        print(f"doc-drift: no changed files for mode={args.mode}, skip")
        return 0

    if args.verbose:
        _print_change_list("doc-drift: changed files:", changed)

    manifest = load_docs_render_manifest(REPO_ROOT)
    render_items = list(manifest.get("renders", []))
    render_state_path = str(manifest["render_state_path"])
    source_paths = {str(path) for item in render_items for path in item.get("source_paths", [])}
    output_paths = {str(item["output_path"]) for item in render_items} | {render_state_path}
    global_sources_changed = bool(GLOBAL_RENDER_SOURCES.intersection(changed))
    expected_outputs = _current_render_outputs()

    relevant_changed = sorted({path for path in changed if path in source_paths or path in output_paths or path in GLOBAL_RENDER_SOURCES})
    if not relevant_changed:
        print("doc-drift: no render-source/output changes, skip")
        return 0

    stale: list[str] = []
    manual: list[str] = []
    if global_sources_changed:
        stale_outputs = _stale_render_outputs()
        stale.extend(f"global-render-source -> {rel_path}" for rel_path in stale_outputs)
    output_has_related_source_change: dict[str, bool] = {}
    for item in render_items:
        item_sources = {str(path) for path in item.get("source_paths", [])}
        item_output = str(item["output_path"])
        output_has_related_source_change[item_output] = output_has_related_source_change.get(item_output, False) or bool(
            item_sources.intersection(changed)
        )
    for item in render_items:
        item_sources = {str(path) for path in item.get("source_paths", [])}
        item_output = str(item["output_path"])
        src_changed = bool(item_sources.intersection(changed))
        out_changed = item_output in changed
        current_output = REPO_ROOT / item_output
        expected_output = expected_outputs.get(item_output)
        is_current = (
            current_output.exists() and expected_output is not None and current_output.read_text(encoding="utf-8") == expected_output
        )
        if src_changed and not is_current:
            stale.append(f"{item['id']} -> {item_output}")
        if out_changed and not output_has_related_source_change.get(item_output, False) and not global_sources_changed and not is_current:
            manual.append(f"manual-output -> {item_output}")
    render_state_changed = render_state_path in changed
    render_state_target = REPO_ROOT / render_state_path
    render_state_expected = expected_outputs.get(render_state_path)
    render_state_current = (
        render_state_target.exists()
        and render_state_expected is not None
        and render_state_target.read_text(encoding="utf-8") == render_state_expected
    )
    if (stale or any(str(path) in source_paths for path in changed)) and not render_state_current:
        stale.append(f"render-state -> {render_state_path}")
    if (
        render_state_changed
        and not any(str(path) in source_paths for path in changed)
        and not global_sources_changed
        and not render_state_current
    ):
        manual.append(f"render-state -> {render_state_path}")

    if stale or manual:
        print("doc-drift: blocked")
        if stale:
            _print_change_list("Detected render sources changed without refreshed outputs:", stale)
        if manual:
            _print_change_list("Detected generated outputs changed without source updates:", manual)
        print("fix: python3 tooling/scripts/render_docs.py")
        return 1

    print("doc-drift: ok (render sources + outputs changed)")
    print("changed:", ", ".join(relevant_changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
