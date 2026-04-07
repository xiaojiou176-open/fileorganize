#!/usr/bin/env python3
"""Generate a single CI evidence bundle JSON from artifacts and CI context.

This script is CI-friendly and local-friendly:
- In CI, it can consume `CI_NEEDS_JSON` and GitHub env vars.
- Locally, it degrades gracefully when files/context are missing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

SENSITIVE_KEY_TOKENS = ("secret", "token", "password", "credential", "api_key", "hmac")


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _find_first_existing(root: Path, candidates: list[str]) -> Path | None:
    for rel in candidates:
        path = root / rel
        if path.exists():
            return path
    return None


def _serialize_repo_path(repo_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _redact_sensitive_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(token in key_text for token in SENSITIVE_KEY_TOKENS):
                sanitized[str(key)] = "<redacted>"
            else:
                sanitized[str(key)] = _redact_sensitive_payload(item)
        return sanitized
    if isinstance(value, list):
        return [_redact_sensitive_payload(item) for item in value]
    return value


def _safe_bundle_projection(bundle: dict[str, Any]) -> dict[str, Any]:
    raw_gates = bundle.get("gates", {})
    safe_gates: dict[str, Any] = {}
    if isinstance(raw_gates, dict):
        for key, value in raw_gates.items():
            if key == "details":
                if not isinstance(value, dict):
                    continue
                safe_details: dict[str, Any] = {}
                if "coverage_threshold" in value:
                    safe_details["coverage_threshold"] = value.get("coverage_threshold")
                if safe_details:
                    safe_gates["details"] = safe_details
                continue
            safe_gates[str(key)] = value
    return {
        "schema_version": bundle.get("schema_version"),
        "timestamp": bundle.get("timestamp"),
        "commit": bundle.get("commit"),
        "branch": bundle.get("branch"),
        "event": bundle.get("event"),
        "summary": bundle.get("summary"),
        "truth": _redact_sensitive_payload(bundle.get("truth", {})),
        "gates": _redact_sensitive_payload(safe_gates),
        "gate_roles": bundle.get("gate_roles", {}),
        "artifacts": bundle.get("artifacts", {}),
        "test_results": bundle.get("test_results", {}),
        "performance": bundle.get("performance", {}),
        "upstream_summary": _redact_sensitive_payload(bundle.get("upstream_summary", {})),
    }


def _safe_receipt_projection(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": receipt.get("schema_version"),
        "generated_at": receipt.get("generated_at"),
        "source_bundle": receipt.get("source_bundle"),
        "source_bundle_truth": _redact_sensitive_payload(receipt.get("source_bundle_truth", {})),
        "upstream_id": receipt.get("upstream_id"),
        "pair_slug": receipt.get("pair_slug"),
        "pair_index": receipt.get("pair_index"),
        "supported_pair": receipt.get("supported_pair", {}),
        "summary": receipt.get("summary", {}),
        "upstream_summary": _redact_sensitive_payload(receipt.get("upstream_summary", {})),
    }


def _resolve_runtime_root(repo_root: Path, artifacts_root: Path) -> Path:
    if artifacts_root.name == ".runtime-cache":
        return artifacts_root
    if artifacts_root.name == "logs" and artifacts_root.parent.name == ".runtime-cache":
        return artifacts_root.parent
    embedded_runtime = artifacts_root / ".runtime-cache"
    if embedded_runtime.exists():
        return embedded_runtime
    repo_runtime = repo_root / ".runtime-cache"
    if artifacts_root == repo_root and repo_runtime.exists():
        return repo_runtime
    return artifacts_root


def _load_ci_run_metrics(runtime_root: Path) -> dict[str, Any] | None:
    candidates = [
        runtime_root / "logs" / "ci-run-metrics.local.json",
        runtime_root / "logs" / "ci-run-metrics.json",
    ]
    best_local: dict[str, Any] | None = None
    for path in candidates:
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        if data.get("status") == "local":
            return data
        if best_local is None:
            best_local = data
    return best_local


def _git_output(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _collect_git_fallback() -> dict[str, str | None]:
    commit = _git_output(["rev-parse", "HEAD"])
    branch = _git_output(["rev-parse", "--abbrev-ref", "HEAD"])
    return {"commit": commit, "branch": branch}


def _collect_ci_context() -> dict[str, Any]:
    fallback = _collect_git_fallback()
    return {
        "commit": os.getenv("GITHUB_SHA") or fallback["commit"],
        "branch": os.getenv("GITHUB_REF_NAME") or fallback["branch"],
        "event": os.getenv("GITHUB_EVENT_NAME") or "local",
        "run_id": os.getenv("GITHUB_RUN_ID"),
        "run_number": os.getenv("GITHUB_RUN_NUMBER"),
        "workflow": os.getenv("GITHUB_WORKFLOW"),
        "repository": os.getenv("GITHUB_REPOSITORY"),
    }


def _load_authoritative_terminal_receipt(runtime_root: Path) -> tuple[Path, dict[str, Any] | None]:
    summary_path = runtime_root / "logs" / "quality-gate" / "summary.json"
    payload = _read_json(summary_path)
    if not isinstance(payload, dict):
        return summary_path, None
    return summary_path, payload


def _build_remote_traceability(context: dict[str, Any]) -> dict[str, Any]:
    has_run_id = bool(context.get("run_id"))
    event = context.get("event")
    if event == "local":
        status = "local-only"
    elif has_run_id:
        status = "github-current-run-linked"
    else:
        status = "missing-github-run-id"
    return {
        "status": status,
        "has_github_run_id": has_run_id,
        "event": event,
        "run_id": context.get("run_id"),
        "run_number": context.get("run_number"),
        "workflow": context.get("workflow"),
        "repository": context.get("repository"),
    }


def _build_authoritative_terminal_receipt(repo_root: Path, runtime_root: Path) -> dict[str, Any]:
    summary_path, payload = _load_authoritative_terminal_receipt(runtime_root)
    try:
        default_path = str(summary_path.relative_to(repo_root))
    except ValueError:
        default_path = str(summary_path)
    if payload is None:
        return {
            "status": "missing",
            "truth_class": "authoritative-terminal-receipt",
            "path": default_path,
            "gate_name": "quality-gate",
            "gate_run_id": None,
            "summary_path": None,
            "latest_summary_path": default_path,
            "execution_mode": None,
            "is_canonical_signal": None,
            "terminal_status": None,
        }
    return {
        "status": "present",
        "truth_class": "authoritative-terminal-receipt",
        "path": str(payload.get("latest_summary_path") or payload.get("summary_path") or default_path),
        "gate_name": payload.get("gate_name"),
        "gate_run_id": payload.get("gate_run_id"),
        "summary_path": payload.get("summary_path"),
        "latest_summary_path": payload.get("latest_summary_path") or default_path,
        "execution_mode": payload.get("execution_mode"),
        "is_canonical_signal": payload.get("is_canonical_signal"),
        "terminal_status": payload.get("status"),
    }


def _determine_source_run_type(context: dict[str, Any]) -> str:
    if context.get("event") == "local":
        return "local"
    if context.get("run_id"):
        return "remote-current-run"
    return "remote-non-current-run"


def _build_truth_surface(repo_root: Path, runtime_root: Path, context: dict[str, Any]) -> dict[str, Any]:
    remote_traceability = _build_remote_traceability(context)
    return {
        "truth_class": "derived-report",
        "source_run_type": _determine_source_run_type(context),
        "authoritative_terminal_receipt": _build_authoritative_terminal_receipt(repo_root, runtime_root),
        "remote_traceability": remote_traceability,
    }


def _parse_coverage(coverage_xml: Path | None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "status": "missing" if coverage_xml is None else "error",
        "source": str(coverage_xml) if coverage_xml else None,
        "line_rate": None,
        "branch_rate": None,
        "lines_covered": None,
        "lines_valid": None,
        "branches_covered": None,
        "branches_valid": None,
    }
    if coverage_xml is None:
        return summary

    try:
        root = ET.parse(coverage_xml).getroot()
    except ET.ParseError:
        return summary

    def _to_percent(value: str | None) -> float | None:
        if value is None:
            return None
        try:
            return round(float(value) * 100.0, 2)
        except ValueError:
            return None

    summary["status"] = "ok"
    summary["line_rate"] = _to_percent(root.attrib.get("line-rate"))
    summary["branch_rate"] = _to_percent(root.attrib.get("branch-rate"))
    summary["lines_covered"] = int(root.attrib.get("lines-covered", "0")) if root.attrib.get("lines-covered") else None
    summary["lines_valid"] = int(root.attrib.get("lines-valid", "0")) if root.attrib.get("lines-valid") else None
    summary["branches_covered"] = int(root.attrib.get("branches-covered", "0")) if root.attrib.get("branches-covered") else None
    summary["branches_valid"] = int(root.attrib.get("branches-valid", "0")) if root.attrib.get("branches-valid") else None
    return summary


def _parse_junit(junit_xml: Path | None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "status": "missing" if junit_xml is None else "error",
        "source": str(junit_xml) if junit_xml else None,
        "tests": None,
        "failures": None,
        "errors": None,
        "skipped": None,
        "time_seconds": None,
    }
    if junit_xml is None:
        return summary

    try:
        root = ET.parse(junit_xml).getroot()
    except ET.ParseError:
        return summary

    if root.tag == "testsuite":
        suite = root
    else:
        first_suite = root.find("testsuite")
        suite = first_suite if first_suite is not None else root

    def _to_int(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(float(value))
        except ValueError:
            return None

    def _to_float(value: str | None) -> float | None:
        if value is None:
            return None
        try:
            return round(float(value), 3)
        except ValueError:
            return None

    summary["status"] = "ok"
    summary["tests"] = _to_int(suite.attrib.get("tests"))
    summary["failures"] = _to_int(suite.attrib.get("failures"))
    summary["errors"] = _to_int(suite.attrib.get("errors"))
    summary["skipped"] = _to_int(suite.attrib.get("skipped"))
    summary["time_seconds"] = _to_float(suite.attrib.get("time"))
    return summary


def _count_plugin_scan_findings(report: Path | None) -> int | None:
    if report is None:
        return None
    data = _read_json(report)
    if not isinstance(data, dict):
        return None
    results = data.get("results")
    if not isinstance(results, dict):
        return None
    total = 0
    for value in results.values():
        if isinstance(value, list):
            total += len(value)
    return total


def _count_gitleaks_findings(report: Path | None) -> int | None:
    if report is None:
        return None
    data = _read_json(report)
    if isinstance(data, list):
        return len(data)
    return None


def _scan_log_for_keywords(path: Path | None, fail_keywords: tuple[str, ...], pass_keywords: tuple[str, ...]) -> str:
    if path is None or not path.exists():
        return "unknown"
    try:
        content = path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return "unknown"

    if any(token in content for token in fail_keywords):
        return "failed"
    if any(token in content for token in pass_keywords):
        return "passed"
    return "unknown"


def _scan_pip_audit_log(path: Path | None) -> str:
    if path is None or not path.exists():
        return "unknown"
    try:
        content = path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return "unknown"

    if "no known vulnerabilities found" in content:
        return "passed"
    if "known vulnerability in" in content or "known vulnerabilities in" in content:
        return "failed"
    if "pip-audit failed" in content:
        return "failed"
    return "unknown"


def _parse_needs_json() -> dict[str, Any]:
    raw = os.getenv("CI_NEEDS_JSON", "")
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def _local_log_status(path: Path | None, fail_keywords: tuple[str, ...], pass_keywords: tuple[str, ...]) -> str:
    if path is None or not path.exists():
        return "unknown"
    return _scan_log_for_keywords(path, fail_keywords=fail_keywords, pass_keywords=pass_keywords)


def _build_local_gate_statuses(runtime_root: Path) -> dict[str, Any]:
    logs_root = runtime_root / "logs"
    quality_log = logs_root / "quality-gate" / "pytest.log"
    functional_log = logs_root / "functional-gate" / "functional-critical.log"
    matrix_log = logs_root / "local-ci-matrix" / "py3.12.log"
    docs_smoke_log = logs_root / "quality-gate" / "docs-smoke.log"
    quality_summary_path, quality_summary = _load_authoritative_terminal_receipt(runtime_root)
    hardening_log = _find_first_existing(
        logs_root,
        [
            "ci-hardening.local.log",
            "quality-gate/ci-hardening.log",
            "pre-push-gate/full-quality-gate.log",
        ],
    )

    if quality_summary is not None and str(quality_summary.get("status", "")).strip():
        quality_status = str(quality_summary.get("status", "")).strip()
    else:
        quality_status = _local_log_status(
            quality_log,
            fail_keywords=("failed", "traceback", "error:"),
            pass_keywords=("passed", "coverage xml written"),
        )

    gates: dict[str, Any] = {
        "quality-gate": quality_status,
        "functional-gate": _local_log_status(
            functional_log,
            fail_keywords=("failed", "traceback", "error:"),
            pass_keywords=("passed",),
        ),
        "local-ci-matrix": _local_log_status(
            matrix_log,
            fail_keywords=("failed", "traceback", "error:"),
            pass_keywords=("passed", "version-parity unit suite passed"),
        ),
        "docs-smoke": _local_log_status(
            docs_smoke_log,
            fail_keywords=("failed", "traceback", "error:"),
            pass_keywords=("passed", "文档命令示例检查通过"),
        ),
        "ci-hardening": _local_log_status(
            hardening_log,
            fail_keywords=("ci-hardening failed", "traceback", "error:", "❌ ci-hardening"),
            pass_keywords=("ci-hardening: passed", "✅ ci-hardening: passed"),
        ),
    }

    if all(value == "passed" for value in gates.values()):
        overall = "passed"
    elif any(value == "failed" for value in gates.values()):
        overall = "failed"
    else:
        overall = "partial"

    gates["overall"] = overall
    summary_rel_path = str(quality_summary_path.relative_to(runtime_root)) if quality_summary_path.exists() else str(quality_summary_path)
    gates["details"] = {
        "quality_gate_summary_path": summary_rel_path,
        "quality_gate_summary_status": quality_summary.get("status") if quality_summary is not None else None,
        "quality_gate_run_id": quality_summary.get("gate_run_id") if quality_summary is not None else None,
        "quality_gate_is_canonical_signal": quality_summary.get("is_canonical_signal") if quality_summary is not None else None,
    }
    return gates


def _build_gate_statuses(artifacts_root: Path, runtime_root: Path) -> dict[str, Any]:
    needs = _parse_needs_json()
    context = _collect_ci_context()
    if context["event"] == "local" and not needs:
        return _build_local_gate_statuses(runtime_root)
    gates: dict[str, Any] = {}

    for job_name in [
        "fork-pr-safety-gate",
        "commit-message-lint",
        "atomic-commit-gate",
        "secrets-supply-chain-gate",
        "lint-backend",
        "lint-frontend",
        "test",
    ]:
        entry = needs.get(job_name, {}) if isinstance(needs, dict) else {}
        result = entry.get("result") if isinstance(entry, dict) else None
        gates[job_name] = result or "unknown"

    gates["overall"] = "passed" if all(value == "success" for value in gates.values()) else "failed"

    gitleaks_report = _find_first_existing(
        runtime_root,
        [
            "logs/gitleaks-report.json",
            "logs/ci-secrets-supply-chain/gitleaks-report.json",
        ],
    )
    plugin_scan_report = _find_first_existing(
        runtime_root,
        [
            "logs/detect-secrets-report.json",
            "logs/ci-secrets-supply-chain/detect-secrets-report.json",
        ],
    )
    coverage_log = _find_first_existing(
        runtime_root,
        [
            "logs/coverage-threshold.log",
        ],
    )

    gates["details"] = {
        "coverage_threshold": _scan_log_for_keywords(
            coverage_log,
            fail_keywords=("failed", "< required"),
            pass_keywords=("coverage-threshold: passed",),
        ),
        "gitleaks_findings": _count_gitleaks_findings(gitleaks_report),
        "plugin_scan_findings": _count_plugin_scan_findings(plugin_scan_report),
    }

    return gates


def _gate_roles() -> dict[str, str]:
    return {
        "quality-gate-full": "canonical-truth",
        "webui-build-test": "supplemental-signal",
        "functional-gate": "supplemental-signal",
        "test": "supplemental-signal",
        "lint-backend": "supporting-gate",
        "lint-frontend": "supporting-gate",
        "fork-pr-safety-gate": "supporting-gate",
        "commit-message-lint": "supporting-gate",
        "atomic-commit-gate": "supporting-gate",
        "secrets-supply-chain-gate": "supporting-gate",
        "ci-hardening-gate": "supporting-gate",
        "packaging-gate": "supporting-gate",
        "mutation-canary-gate": "supporting-gate",
        "live-smoke-preflight": "supporting-gate",
    }


def _build_security_summary(runtime_root: Path) -> dict[str, Any]:
    gitleaks_report = _find_first_existing(
        runtime_root,
        [
            "logs/gitleaks-report.json",
            "logs/ci-secrets-supply-chain/gitleaks-report.json",
        ],
    )
    plugin_scan_report = _find_first_existing(
        runtime_root,
        [
            "logs/detect-secrets-report.json",
            "logs/ci-secrets-supply-chain/detect-secrets-report.json",
        ],
    )
    pip_audit_log = _find_first_existing(
        runtime_root,
        [
            "logs/pip-audit-primary.log",
            "logs/quality-gate/pip-audit.log",
        ],
    )

    gitleaks_findings = _count_gitleaks_findings(gitleaks_report)
    plugin_scan_findings = _count_plugin_scan_findings(plugin_scan_report)

    pip_audit_state = _scan_pip_audit_log(pip_audit_log)

    return {
        "gitleaks": {
            "report": str(gitleaks_report) if gitleaks_report else None,
            "findings": gitleaks_findings,
            "status": "passed" if gitleaks_findings == 0 else ("failed" if gitleaks_findings is not None else "unknown"),
        },
        "plugin_scan": {
            "report_present": plugin_scan_report is not None,
            "findings": plugin_scan_findings,
            "status": "passed" if plugin_scan_findings == 0 else ("failed" if plugin_scan_findings is not None else "unknown"),
        },
        "pip_audit": {
            "log": str(pip_audit_log) if pip_audit_log else None,
            "status": pip_audit_state,
        },
    }


def _list_collected_files(artifacts_root: Path) -> list[str]:
    if not artifacts_root.exists():
        return []
    collected: list[str] = []
    for path in artifacts_root.rglob("*"):
        if path.is_file():
            collected.append(str(path.relative_to(artifacts_root)))
    collected.sort()
    return collected


def _build_failure_summary(
    gates: dict[str, Any],
    security: dict[str, Any],
    tests: dict[str, Any],
    coverage: dict[str, Any],
) -> dict[str, Any]:
    failing_gates = sorted(
        key for key, value in gates.items() if key not in {"overall", "details"} and value in {"failed", "failure", "error", "cancelled"}
    )
    suspected_domains: list[str] = []
    if failing_gates:
        suspected_domains.append("ci_environment")
    if security.get("gitleaks", {}).get("status") == "failed" or security.get("plugin_scan", {}).get("status") == "failed":
        suspected_domains.append("repo_config")
    if tests.get("status") == "error":
        suspected_domains.append("repo_logic")
    if coverage.get("status") in {"missing", "error"}:
        suspected_domains.append("cache_state")
    if not suspected_domains:
        suspected_domains.append("repo_logic")
    security_failed = any(value.get("status") == "failed" for value in security.values() if isinstance(value, dict))
    overall_status = "failed" if failing_gates or security_failed else "passed"
    return {
        "overall_status": overall_status,
        "failing_gates": failing_gates,
        "suspected_domains": suspected_domains,
    }


def _build_upstream_summary(repo_root: Path) -> dict[str, Any]:
    inventory_path = repo_root / "contracts" / "upstreams" / "upstream_inventory.yaml"
    if not inventory_path.exists():
        return {
            "status": "missing",
            "inventory_path": _serialize_repo_path(repo_root, inventory_path),
            "count": 0,
            "upstreams": [],
        }
    payload = yaml.safe_load(inventory_path.read_text(encoding="utf-8")) or {}
    items = payload.get("upstreams", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []
    upstreams = []
    for item in items:
        if not isinstance(item, dict):
            continue
        upstreams.append(
            {
                "id": item.get("id"),
                "class": item.get("class"),
                "role": item.get("role"),
                "pin_kind": item.get("pin_kind"),
                "pinned_value": item.get("pinned_value"),
                "verification_suite": item.get("verification_suite"),
                "failure_domain": item.get("failure_domain"),
            }
        )
    return {
        "status": "ok",
        "inventory_path": _serialize_repo_path(repo_root, inventory_path),
        "count": len(upstreams),
        "upstreams": upstreams,
    }


def _load_upstream_inventory(repo_root: Path) -> tuple[Path, dict[str, dict[str, Any]]]:
    inventory_path = repo_root / "contracts" / "upstreams" / "upstream_inventory.yaml"
    if not inventory_path.exists():
        return inventory_path, {}
    payload = yaml.safe_load(inventory_path.read_text(encoding="utf-8")) or {}
    items = payload.get("upstreams", []) if isinstance(payload, dict) else []
    by_id: dict[str, dict[str, Any]] = {}
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            upstream_id = str(item.get("id", "")).strip()
            if upstream_id:
                by_id[upstream_id] = item
    return inventory_path, by_id


def _load_compatibility_matrix(repo_root: Path) -> list[dict[str, Any]]:
    matrix_path = repo_root / "contracts" / "upstreams" / "compatibility_matrix.yaml"
    if not matrix_path.exists():
        return []
    payload = yaml.safe_load(matrix_path.read_text(encoding="utf-8")) or {}
    items = payload.get("matrix", []) if isinstance(payload, dict) else []
    return [item for item in items if isinstance(item, dict)]


def _load_failure_ownership(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = repo_root / "contracts" / "upstreams" / "failure_ownership.yaml"
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    ownership = payload.get("ownership", {}) if isinstance(payload, dict) else {}
    return {str(key): value for key, value in ownership.items() if isinstance(value, dict)}


def _receipt_slug(upstream_id: str, pair: dict[str, Any], idx: int) -> str:
    ignored = {
        "verification_suite",
        "verification_mode",
        "verification_artifact",
        "verification_max_age_hours",
        "rollback_baseline",
    }
    semantic_keys = [key for key in pair if key not in ignored]
    parts = [upstream_id]
    for key in sorted(semantic_keys):
        raw = str(pair.get(key, "")).strip()
        if not raw:
            continue
        normalized = re.sub(r"[^A-Za-z0-9]+", "-", raw).strip("-").lower()
        if normalized:
            parts.append(normalized)
    if len(parts) == 1:
        parts.append(f"pair-{idx}")
    return "-".join(parts)


def _write_upstream_receipts(repo_root: Path, bundle: dict[str, Any], bundle_output: Path) -> list[str]:
    inventory_path, inventory_by_id = _load_upstream_inventory(repo_root)
    matrix_items = _load_compatibility_matrix(repo_root)
    failure_ownership = _load_failure_ownership(repo_root)
    written: list[str] = []
    generated_at = datetime.now(timezone.utc).isoformat()
    for entry in matrix_items:
        upstream_id = str(entry.get("upstream_id", "")).strip()
        if not upstream_id:
            continue
        inventory_item = inventory_by_id.get(upstream_id, {})
        supported_pairs = entry.get("supported_pairs", [])
        if not isinstance(supported_pairs, list):
            continue
        for idx, pair in enumerate(supported_pairs, 1):
            if not isinstance(pair, dict):
                continue
            artifact_raw = str(pair.get("verification_artifact", "")).strip()
            if not artifact_raw:
                continue
            artifact_path = Path(artifact_raw)
            if not artifact_path.is_absolute():
                artifact_path = repo_root / artifact_path
            receipt = {
                "schema_version": "1.0",
                "generated_at": generated_at,
                "source_bundle": _serialize_repo_path(repo_root, bundle_output),
                "source_bundle_truth": bundle.get("truth", {}),
                "upstream_id": upstream_id,
                "pair_slug": _receipt_slug(upstream_id, pair, idx),
                "pair_index": idx,
                "supported_pair": pair,
                "summary": bundle.get("summary", {}),
                "upstream_summary": {
                    "status": "ok",
                    "inventory_path": _serialize_repo_path(repo_root, inventory_path),
                    "upstream": {
                        "id": inventory_item.get("id"),
                        "class": inventory_item.get("class"),
                        "role": inventory_item.get("role"),
                        "pin_kind": inventory_item.get("pin_kind"),
                        "pinned_value": inventory_item.get("pinned_value"),
                        "verification_suite": inventory_item.get("verification_suite"),
                        "failure_domain": inventory_item.get("failure_domain"),
                    },
                    "failure_ownership": failure_ownership.get(upstream_id, {}),
                },
                "context": bundle.get("context", {}),
                "failure_summary": bundle.get("failure_summary", {}),
            }
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(
                json.dumps(_safe_receipt_projection(receipt), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            written.append(str(artifact_path))
    return written


def build_bundle(artifacts_root: Path) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    runtime_root = _resolve_runtime_root(repo_root, artifacts_root)
    coverage_xml = _find_first_existing(
        runtime_root,
        [
            "ci/coverage.xml",
        ],
    )
    junit_xml = _find_first_existing(
        runtime_root,
        [
            "ci/pytest-junit.xml",
            "ci/pytest-junit-fast.xml",
            "ci/pytest-functional-critical-junit.xml",
        ],
    )

    context = _collect_ci_context()
    gates = _build_gate_statuses(artifacts_root, runtime_root)
    coverage = _parse_coverage(coverage_xml)
    tests = _parse_junit(junit_xml)
    security = _build_security_summary(runtime_root)
    metrics = _load_ci_run_metrics(runtime_root)
    truth = _build_truth_surface(repo_root, runtime_root, context)
    artifacts = {
        "artifacts_root": str(artifacts_root),
        "runtime_root": str(runtime_root),
        "files": _list_collected_files(artifacts_root),
    }
    upstream_summary = _build_upstream_summary(repo_root)
    failure_summary = _build_failure_summary(gates, security, tests, coverage)
    events = {
        "run_id": context.get("run_id"),
        "traceability": truth["remote_traceability"],
        "log_files": [path for path in artifacts["files"] if path.endswith((".log", ".jsonl", ".json"))],
    }

    return {
        "schema_version": "2.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit": context["commit"],
        "branch": context["branch"],
        "event": context["event"],
        "context": context,
        "summary": {
            "overall_status": failure_summary["overall_status"],
            "gate_overall": gates.get("overall"),
        },
        "truth": truth,
        "gates": gates,
        "gate_roles": _gate_roles(),
        "events": events,
        "artifacts": artifacts,
        "test_results": {"coverage": coverage, "pytest": tests},
        "security": security,
        "performance": {"metrics": metrics},
        "failure_summary": failure_summary,
        "upstream_summary": upstream_summary,
        "sources": artifacts,
        # Backward-compatible projections for older consumers.
        "coverage": coverage,
        "tests": tests,
        "metrics": metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CI evidence bundle JSON")
    parser.add_argument(
        "--artifacts-root",
        default=".",
        help="Directory containing CI/runtime outputs (default: repo root)",
    )
    parser.add_argument(
        "--output",
        default=".runtime-cache/ci/evidence-bundle.json",
        help="Output bundle JSON path (default: .runtime-cache/ci/evidence-bundle.json)",
    )
    args = parser.parse_args()

    artifacts_root = Path(args.artifacts_root).resolve()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    bundle = build_bundle(artifacts_root)
    output.write_text(json.dumps(_safe_bundle_projection(bundle), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipts = _write_upstream_receipts(Path(__file__).resolve().parents[2], bundle, output)

    print(f"✅ evidence bundle generated: {output}")
    print(f"   artifacts_root={artifacts_root}")
    print(f"   upstream_receipts={len(receipts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
