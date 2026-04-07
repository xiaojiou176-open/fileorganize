#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

NETWORK_PATTERNS = (
    "live_error_class=network-timeout",
    "timed out",
    "timeout",
    "upstream unavailable",
    "service unavailable",
    "gateway timeout",
    "deadline exceeded",
)

NETWORK_JITTER_PATTERNS = (
    "live_error_class=network-jitter",
    "econn",
    "enotfound",
    "eai_again",
    "net::",
    "connection reset",
    "connection refused",
    "err_network_changed",
    "err_name_not_resolved",
    "dns",
    "name resolution",
    "unreachable",
)

BUSINESS_PATTERNS = (
    "live_error_class=business",
    "assertionerror",
    "preflight failed",
    "request not ok",
    "server error",
    "empty page title",
    "empty body text",
    "invalid format",
)


def classify_live_failure(text: str) -> str:
    normalized = text.lower()
    # When both markers exist in a single log, classify by the latest marker.
    # This avoids retrying after a later business failure that should stop retry.
    latest_jitter = normalized.rfind("live_error_class=network-jitter")
    latest_network = normalized.rfind("live_error_class=network-timeout")
    latest_business = normalized.rfind("live_error_class=business")
    if latest_jitter >= 0 or latest_network >= 0 or latest_business >= 0:
        ranked = [(latest_business, "business"), (latest_jitter, "network-jitter"), (latest_network, "network-timeout")]
        ranked.sort(key=lambda item: item[0], reverse=True)
        if ranked[0][0] >= 0:
            return ranked[0][1]
    has_jitter = any(token in normalized for token in NETWORK_JITTER_PATTERNS)
    has_network = any(token in normalized for token in NETWORK_PATTERNS)
    has_business = any(token in normalized for token in BUSINESS_PATTERNS)
    if has_business:
        return "business"
    if has_jitter:
        return "network-jitter"
    if has_network:
        return "network-timeout"
    return "unknown"


def classify_live_failure_file(log_file: Path) -> str:
    if not log_file.exists():
        return "unknown"
    content = log_file.read_text(encoding="utf-8", errors="ignore")
    return classify_live_failure(content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify live test failures from log output.")
    parser.add_argument("--log-file", required=True, help="Path to live test log file")
    args = parser.parse_args()
    print(classify_live_failure_file(Path(args.log_file)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
