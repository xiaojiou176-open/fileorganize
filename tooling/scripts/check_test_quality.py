#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

TEST_DIR = Path("tests")
JS_TEST_GLOBS = (
    "**/*.test.js",
    "**/*.test.jsx",
    "**/*.test.ts",
    "**/*.test.tsx",
    "**/__tests__/**/*.js",
    "**/__tests__/**/*.jsx",
    "**/__tests__/**/*.ts",
    "**/__tests__/**/*.tsx",
)


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    rule: str
    snippet: str


ALLOW_TOBEDEFINED_MARKER = "test-quality: allow-toBeDefined"
ALLOW_NO_ASSERT_MARKER = "test-quality: allow-no-assert"


def _is_same_name_or_attr(left: ast.expr, right: ast.expr) -> bool:
    if isinstance(left, ast.Name) and isinstance(right, ast.Name):
        return left.id == right.id
    if isinstance(left, ast.Attribute) and isinstance(right, ast.Attribute):
        return (
            isinstance(left.value, ast.Name)
            and isinstance(right.value, ast.Name)
            and left.value.id == right.value.id
            and left.attr == right.attr
        )
    return False


def _is_same_literal(left: ast.expr, right: ast.expr) -> bool:
    if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
        return left.value == right.value
    return False


def _is_truthy_constant(node: ast.expr) -> bool:
    if not isinstance(node, ast.Constant):
        return False
    value = node.value
    if isinstance(value, bool):
        return value is True
    return bool(value)


def _is_falsy_constant(node: ast.expr) -> bool:
    if not isinstance(node, ast.Constant):
        return False
    value = node.value
    if isinstance(value, bool):
        return value is False
    return not bool(value)


def _snippet(source: str, line: int) -> str:
    lines = source.splitlines()
    if 1 <= line <= len(lines):
        return lines[line - 1].strip()
    return ""


def _iter_python_test_functions(tree: ast.AST) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            yield node


def _call_name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        base = _call_name(func.value)
        return f"{base}.{func.attr}" if base else func.attr
    return ""


def _is_assertion_like_call(node: ast.Call) -> bool:
    name = _call_name(node.func)
    if not name:
        return False
    leaf = name.rsplit(".", 1)[-1]
    if leaf.startswith("assert"):
        return True
    if re.search(r"(^|_)assert($|_)", leaf):
        return True
    if leaf == "fail":
        return True
    if leaf == "raises":
        return True
    if leaf.startswith("assert_"):
        return True
    return False


def _contains_effective_assertion(test_fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for item in ast.walk(test_fn):
        if isinstance(item, ast.Assert):
            return True
        if isinstance(item, ast.Call) and _is_assertion_like_call(item):
            return True
    return False


def _is_passive_except_handler(handler: ast.ExceptHandler) -> bool:
    if not handler.body:
        return True
    for stmt in handler.body:
        if isinstance(stmt, (ast.Pass, ast.Break, ast.Continue)):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue
        return False
    return True


def _looks_like_no_throw_false_green(test_fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for item in ast.walk(test_fn):
        if not isinstance(item, ast.Try):
            continue
        has_try_call = any(isinstance(node, ast.Call) for stmt in item.body for node in ast.walk(stmt))
        if not has_try_call:
            continue
        if item.handlers and all(_is_passive_except_handler(handler) for handler in item.handlers):
            return True
    return False


def _has_line_marker(source: str, node: ast.FunctionDef | ast.AsyncFunctionDef, marker: str) -> bool:
    start = max(1, int(getattr(node, "lineno", 1)))
    end = max(start, int(getattr(node, "end_lineno", start)))
    lines = source.splitlines()
    span = lines[start - 1 : end]
    for line in span:
        hash_idx = line.find("#")
        if hash_idx < 0:
            continue
        if marker in line[hash_idx + 1 :]:
            return True
    return False


def scan_python_file(path: Path) -> list[Finding]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    findings: list[Finding] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            if isinstance(node.test, ast.Constant) and node.test.value is True:
                findings.append(Finding(path, node.lineno, "PY_ASSERT_TRUE", _snippet(source, node.lineno)))
            elif _is_truthy_constant(node.test):
                findings.append(
                    Finding(
                        path,
                        node.lineno,
                        "PY_ASSERT_TRUTHY_CONSTANT",
                        _snippet(source, node.lineno),
                    )
                )
            if isinstance(node.test, ast.Compare) and len(node.test.ops) == 1 and isinstance(node.test.ops[0], (ast.Eq, ast.Is)):
                left = node.test.left
                right = node.test.comparators[0]
                if _is_same_name_or_attr(left, right):
                    findings.append(Finding(path, node.lineno, "PY_SELF_EQUAL", _snippet(source, node.lineno)))
                if _is_same_literal(left, right):
                    findings.append(Finding(path, node.lineno, "PY_LITERAL_SELF_EQUAL", _snippet(source, node.lineno)))

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method = node.func.attr
            args = node.args
            if method == "assertTrue" and len(args) >= 1:
                if isinstance(args[0], ast.Constant) and args[0].value is True:
                    findings.append(Finding(path, node.lineno, "PY_ASSERTTRUE_TRUE", _snippet(source, node.lineno)))
                elif _is_truthy_constant(args[0]):
                    findings.append(
                        Finding(
                            path,
                            node.lineno,
                            "PY_ASSERTTRUE_TRUTHY_CONSTANT",
                            _snippet(source, node.lineno),
                        )
                    )
            if method == "assertFalse" and len(args) >= 1:
                if isinstance(args[0], ast.Constant) and args[0].value is False:
                    findings.append(Finding(path, node.lineno, "PY_ASSERTFALSE_FALSE", _snippet(source, node.lineno)))
                elif _is_falsy_constant(args[0]):
                    findings.append(
                        Finding(
                            path,
                            node.lineno,
                            "PY_ASSERTFALSE_FALSY_CONSTANT",
                            _snippet(source, node.lineno),
                        )
                    )
            if method in {"assertEqual", "assertIs"} and len(args) >= 2:
                if _is_same_name_or_attr(args[0], args[1]):
                    findings.append(Finding(path, node.lineno, "PY_SELF_EQUAL", _snippet(source, node.lineno)))
                if _is_same_literal(args[0], args[1]):
                    findings.append(Finding(path, node.lineno, "PY_LITERAL_SELF_EQUAL", _snippet(source, node.lineno)))

    for test_fn in _iter_python_test_functions(tree):
        if _has_line_marker(source, test_fn, ALLOW_NO_ASSERT_MARKER):
            continue
        has_assertion = _contains_effective_assertion(test_fn)
        if has_assertion:
            continue
        if _looks_like_no_throw_false_green(test_fn):
            findings.append(Finding(path, test_fn.lineno, "PY_NO_THROW_FALSE_GREEN", _snippet(source, test_fn.lineno)))
            continue
        findings.append(Finding(path, test_fn.lineno, "PY_NO_ASSERTION", _snippet(source, test_fn.lineno)))

    return findings


JS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "JS_EXPECT_TRUE",
        re.compile(r"expect\s*\(\s*true\s*\)\s*\.\s*toBe\s*\(\s*true\s*\)", re.IGNORECASE),
    ),
    (
        "JS_EXPECT_FALSE",
        re.compile(r"expect\s*\(\s*false\s*\)\s*\.\s*toBe\s*\(\s*false\s*\)", re.IGNORECASE),
    ),
    (
        "JS_SELF_EQUAL",
        re.compile(
            r"expect\s*\(\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)\s*\)\s*\.\s*to(Be|Equal|StrictEqual)\s*\(\s*\1\s*\)",
            re.IGNORECASE,
        ),
    ),
    (
        "JS_LITERAL_SELF_EQUAL",
        re.compile(
            r"expect\s*\(\s*(true|false|null|undefined|-?\d+(?:\.\d+)?|\"[^\"]*\"|'[^']*')\s*\)\s*\.\s*to(Be|Equal|StrictEqual)\s*\(\s*\1\s*\)",
            re.IGNORECASE,
        ),
    ),
    (
        "JS_TOBEDEFINED",
        re.compile(
            r"expect\s*\(\s*.+?\s*\)\s*\.\s*toBeDefined\s*\(\s*\)",
            re.IGNORECASE,
        ),
    ),
)


def scan_js_text(path: Path, content: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = content.splitlines()

    def _has_allowed_js_comment(line: str) -> bool:
        in_single = False
        in_double = False
        escaped = False
        comment_idx = -1
        for idx, ch in enumerate(line):
            if escaped:
                escaped = False
                continue
            if ch == "\\" and (in_single or in_double):
                escaped = True
                continue
            if ch == "'" and not in_double:
                in_single = not in_single
                continue
            if ch == '"' and not in_single:
                in_double = not in_double
                continue
            if in_single or in_double:
                continue
            if ch == "/" and idx + 1 < len(line) and line[idx + 1] in {"/", "*"}:
                comment_idx = idx + 2
                break
            if ch == "#":
                comment_idx = idx + 1
                break
        return comment_idx >= 0 and ALLOW_TOBEDEFINED_MARKER in line[comment_idx:]

    for rule, pattern in JS_PATTERNS:
        for match in pattern.finditer(content):
            line_no = content.count("\n", 0, match.start()) + 1
            line = lines[line_no - 1].strip() if 1 <= line_no <= len(lines) else ""
            if rule == "JS_TOBEDEFINED":
                if _has_allowed_js_comment(line):
                    continue
            snippet = match.group(0).replace("\n", " ").strip()
            findings.append(Finding(path, line_no, rule, snippet or line))
    return findings


def iter_python_test_files(root: Path) -> Iterable[Path]:
    test_root = root / TEST_DIR
    if not test_root.exists():
        return []
    found: set[Path] = set(test_root.rglob("test*.py"))
    found.update(test_root.rglob("*_test.py"))
    return sorted(found)


def iter_js_test_files(root: Path) -> list[Path]:
    found: set[Path] = set()
    for glob in JS_TEST_GLOBS:
        try:
            found.update(root.glob(glob))
        except FileNotFoundError:
            # Some build directories may disappear during CI bootstrap; ignore and continue.
            continue
    excluded_parts = {"node_modules", ".venv", ".git", "build", "dist", "artifacts"}
    return sorted(path for path in found if path.is_file() and not excluded_parts.intersection(path.parts))


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect placebo test assertions and fail the build.")
    parser.add_argument("--root", default=".", help="Repository root to scan (default: current directory)")
    parser.add_argument("--only-python", action="store_true", help="Scan Python tests only")
    parser.add_argument("--only-js", action="store_true", help="Scan JavaScript/TypeScript tests only")
    args = parser.parse_args()

    if args.only_python and args.only_js:
        parser.error("--only-python and --only-js cannot be used together")

    root = Path(args.root).resolve()
    findings: list[Finding] = []

    scan_python = not args.only_js
    scan_js = not args.only_python

    if scan_python:
        for py_file in iter_python_test_files(root):
            findings.extend(scan_python_file(py_file))

    if scan_js:
        for js_file in iter_js_test_files(root):
            text = js_file.read_text(encoding="utf-8", errors="ignore")
            findings.extend(scan_js_text(js_file, text))

    if findings:
        print("❌ test_quality_gate: found placebo assertions")
        for item in findings:
            rel = item.path.relative_to(root)
            print(f"- {rel}:{item.line} [{item.rule}] {item.snippet}")
        return 1

    print("✅ test_quality_gate: no placebo assertions detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
