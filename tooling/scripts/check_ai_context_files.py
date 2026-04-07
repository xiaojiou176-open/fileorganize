#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _registry_path(repo_root: Path) -> Path:
    modern = repo_root / "contracts" / "governance" / "ai_context_registry.json"
    legacy = repo_root / "脚本" / "config" / "ai_context_registry.json"
    if modern.exists():
        return modern
    return legacy


def main() -> int:
    registry = json.loads(_registry_path(REPO_ROOT).read_text(encoding="utf-8"))
    required_any = [str(path) for path in registry.get("required_any", [])]
    required_all = [str(path) for path in registry.get("required_all", [])]
    missing: list[str] = []
    if required_any and not any((REPO_ROOT / rel).exists() for rel in required_any):
        missing.append("missing any-of: " + " / ".join(required_any))
    for rel in required_all:
        if not (REPO_ROOT / rel).exists():
            missing.append(rel)
    if missing:
        print("❌ check-ai-context-files: missing required AI context files")
        for item in missing:
            print(f"- {item}")
        return 1
    print("✅ check-ai-context-files: passed")
    print(f"required_all={len(required_all)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
