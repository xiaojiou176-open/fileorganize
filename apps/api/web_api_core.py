# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path, PurePath
from typing import Any, Callable, Dict, List, Sequence

from packages.infrastructure.manifest_store import read_jsonl

CommandExecutor = Callable[..., None]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _within_root(target: Path, root: Path) -> bool:
    resolved_root = root.resolve()
    candidate = target if target.is_absolute() else resolved_root / target
    try:
        relative = PurePath(candidate).relative_to(PurePath(resolved_root))
    except ValueError:
        return False
    return Path(*relative.parts) == _safe_relative_descendant(PurePath(*relative.parts).as_posix())


def _sanitize_filename(name: str, index: int) -> str:
    candidate = Path(name or "").name.strip()
    if not candidate:
        return f"upload-{index:04d}.bin"
    return candidate


def _safe_float_progress(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return round(value, 4)


def _write_json_atomic(path: Path, payload: Any, *, root: Path) -> None:
    resolved_root = root.resolve()
    candidate = path if path.is_absolute() else resolved_root / path
    try:
        relative = PurePath(candidate).relative_to(PurePath(resolved_root))
    except ValueError as exc:
        raise ValueError(f"write target {candidate} is outside controlled root {resolved_root}") from exc
    safe_relative = _safe_relative_descendant(PurePath(*relative.parts).as_posix())
    if safe_relative != Path(*relative.parts):
        raise ValueError(f"write target {candidate} is outside controlled root {resolved_root}")
    resolved_path = resolved_root / safe_relative
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_relative = safe_relative.with_suffix(safe_relative.suffix + ".tmp")
    tmp_path = resolved_root / tmp_relative
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(resolved_path)


def _safe_relative_descendant(raw: str | None) -> Path:
    text = str(raw or "").strip().replace("\\", "/")
    if not text:
        return Path()
    parts = [part for part in PurePath(text).parts if part not in {"", ".", ".."}]
    return Path(*parts)


def _read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_jsonl_rows(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_manifest_rows(manifest_path: Path) -> List[Dict[str, Any]]:
    return [dict(row) for row in read_jsonl(manifest_path, validate=True)]


def _parse_form_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default
