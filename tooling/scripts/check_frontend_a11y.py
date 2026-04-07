#!/usr/bin/env python3
"""Deterministic frontend accessibility gate (static checks)."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

FRONTEND_EXTENSIONS = {
    ".html",
    ".htm",
    ".vue",
    ".svelte",
    ".astro",
    ".jsx",
    ".tsx",
}


def _line_no(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def _iter_targets(files: list[str]) -> list[Path]:
    targets: list[Path] = []
    for raw in files:
        p = Path(raw)
        if p.suffix.lower() in FRONTEND_EXTENSIONS and p.exists() and p.is_file():
            targets.append(p)
    return targets


def _parse_viewport_directives(content: str) -> dict[str, str]:
    directives: dict[str, str] = {}
    for part in content.split(","):
        chunk = part.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            directives[chunk.lower()] = "true"
            continue
        key, value = chunk.split("=", 1)
        directives[key.strip().lower()] = value.strip().lower()
    return directives


def _extract_attr(tag: str, attr: str) -> str:
    pattern = re.compile(rf"\b{re.escape(attr)}\s*=\s*(['\"])(.*?)\1", re.IGNORECASE | re.DOTALL)
    m = pattern.search(tag)
    if not m:
        return ""
    return m.group(2).strip()


def _has_focus_replacement_class(class_value: str) -> bool:
    normalized = " ".join(class_value.split())
    return any(
        token in normalized
        for token in (
            "focus:ring",
            "focus-visible:ring",
            "focus-visible:outline-",
            "focus:outline-[",
            "focus-visible:outline-[",
            "focus:shadow-",
            "focus-visible:shadow-",
        )
    )


def _has_accessible_name(tag: str) -> bool:
    return bool(
        re.search(
            r"\b(?:aria-label|aria-labelledby|title)\s*=\s*(?:['\"].+?['\"]|\{[^}]+\})",
            tag,
            flags=re.IGNORECASE,
        )
    )


def _check_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    issues: list[str] = []

    for m in re.finditer(r"<img\b[^>]*>", text, flags=re.IGNORECASE):
        tag = m.group(0)
        if not re.search(r"\balt\s*=\s*(?:['\"].*?['\"]|\{[^}]+\})", tag, flags=re.IGNORECASE):
            issues.append(f"{path}:{_line_no(text, m.start())} img missing alt attribute")

    for m in re.finditer(r"<button\b[^>]*>", text):
        tag = m.group(0)
        if not re.search(
            r"\btype\s*=\s*(?:(['\"])(button|submit|reset)\1|\{\s*(['\"])(button|submit|reset)\3\s*\})",
            tag,
            flags=re.IGNORECASE,
        ):
            issues.append(f"{path}:{_line_no(text, m.start())} button missing explicit type")

    for m in re.finditer(r"<button\b([^>]*)>(.*?)</button>", text, flags=re.DOTALL):
        attrs = m.group(1) or ""
        content = m.group(2) or ""
        has_accessible_name = _has_accessible_name(attrs)
        text_content = re.sub(r"<[^>]+>", "", content, flags=re.DOTALL).strip()
        if not has_accessible_name and not text_content:
            issues.append(f"{path}:{_line_no(text, m.start())} icon-only button missing accessible name")

    for m in re.finditer(r"<a\b([^>]*)>(.*?)</a>", text, flags=re.IGNORECASE | re.DOTALL):
        attrs = m.group(1) or ""
        content = m.group(2) or ""
        has_href = re.search(r"\bhref\s*=\s*(?:['\"].+?['\"]|\{[^}]+\})", attrs, flags=re.IGNORECASE)
        if has_href is None:
            continue
        has_accessible_name = _has_accessible_name(attrs)
        text_content = re.sub(r"<[^>]+>", "", content, flags=re.DOTALL).strip()
        if not has_accessible_name and not text_content:
            issues.append(f"{path}:{_line_no(text, m.start())} icon-only link missing accessible name")

    for m in re.finditer(r"\btabindex\s*=\s*(['\"])\s*([1-9][0-9]*)\s*\1", text, flags=re.IGNORECASE):
        issues.append(f"{path}:{_line_no(text, m.start())} positive tabindex is not allowed")

    for m in re.finditer(r"<(?:button|a|input|select|textarea)\b[^>]*>", text, flags=re.IGNORECASE):
        tag = m.group(0)
        class_value = _extract_attr(tag, "class") or _extract_attr(tag, "className")
        has_removed_focus = "focus:outline-none" in class_value or "focus-visible:outline-none" in class_value
        has_replacement_focus = _has_focus_replacement_class(class_value)
        if has_removed_focus and not has_replacement_focus:
            issues.append(f"{path}:{_line_no(text, m.start())} focus outline removed without replacement focus indicator")
            continue

        style_value = _extract_attr(tag, "style").lower().replace(" ", "")
        if "outline:none" in style_value or "outline:0" in style_value:
            issues.append(f"{path}:{_line_no(text, m.start())} inline style removes outline; provide visible focus style")

    if path.suffix.lower() in {".html", ".htm"}:
        html_match = re.search(r"<html\b[^>]*>", text, flags=re.IGNORECASE)
        if html_match and not re.search(r"\blang\s*=\s*(['\"]).+?\1", html_match.group(0), flags=re.IGNORECASE):
            issues.append(f"{path}:{_line_no(text, html_match.start())} html missing lang attribute")

        if "<head" in text.lower():
            viewport = re.search(
                r'<meta\b[^>]*name\s*=\s*([\'"])viewport\1[^>]*content\s*=\s*([\'"])(.*?)\2[^>]*>',
                text,
                flags=re.IGNORECASE,
            )
            if viewport is None:
                issues.append(f"{path}:1 missing viewport meta")
            else:
                directives = _parse_viewport_directives(viewport.group(3))
                user_scalable = directives.get("user-scalable", "").strip().lower()
                if user_scalable in {"no", "0", "false"}:
                    issues.append(f"{path}:1 viewport must not disable zoom via user-scalable=no/0/false")
                max_scale = directives.get("maximum-scale", "").strip()
                if max_scale:
                    try:
                        if float(max_scale) < 2:
                            issues.append(f"{path}:1 viewport maximum-scale should be >=2 to preserve zoom")
                    except ValueError:
                        issues.append(f"{path}:1 viewport maximum-scale must be numeric")

    control_ids_requiring_labels: set[str] = set()
    for m in re.finditer(
        r"<(?:input|select|textarea)\b[^>]*\bid\s*=\s*(['\"])([^'\"]+)\1[^>]*>",
        text,
        flags=re.IGNORECASE,
    ):
        tag = m.group(0)
        control_id = m.group(2).strip()
        if control_id and not _has_accessible_name(tag):
            control_ids_requiring_labels.add(control_id)

    label_for = set(
        m.group(2).strip() for m in re.finditer(r"<label\b[^>]*\b(?:for|htmlFor)\s*=\s*(['\"])([^'\"]+)\1", text, flags=re.IGNORECASE)
    )
    for missing in sorted(control_ids_requiring_labels - label_for):
        issues.append(f"{path}:1 form control id '{missing}' has no matching label[for]")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help="Frontend files")
    args = parser.parse_args()

    targets = _iter_targets(args.files)
    if not targets:
        print("check_frontend_a11y: no frontend files in scope, skip")
        return 0

    failures: list[str] = []
    for target in targets:
        failures.extend(_check_file(target))

    if failures:
        print("❌ check_frontend_a11y: failed")
        for line in failures:
            print(f"- {line}")
        return 1

    print(f"✅ check_frontend_a11y: passed ({len(targets)} file(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
