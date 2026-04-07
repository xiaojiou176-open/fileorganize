# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from pathlib import Path, PurePath
from typing import Any, Callable, Dict, List, Protocol, Sequence

from fastapi import HTTPException

from apps.api.web_api_models import JobRecord
from apps.api.web_api_store import JobStore

MANIFEST_EDITABLE_EXTRA_FIELDS = {"ai", "new_path", "ignore"}


class JsonAtomicWriter(Protocol):
    def __call__(self, path: Path, payload: Any, *, root: Path) -> None: ...


def _resolve_allowed_existing_path(
    raw: str,
    *,
    label: str,
    allowed_roots: Sequence[Path] | None,
    within_root: Callable[[Path, Path], bool] | None,
    prefer_missing_not_found: bool = False,
) -> Path:
    raw_text = os.path.expanduser(str(raw).strip())
    candidate = PurePath(raw_text)
    roots = list(allowed_roots or [])
    candidates: list[Path]
    saw_allowed_candidate = False
    if candidate.is_absolute() or not roots:
        candidates = [Path(raw_text)]
    else:
        safe_parts = [part for part in candidate.parts if part not in {"", ".", ".."}]
        candidates = [root.joinpath(*safe_parts) for root in roots]

    for unresolved in candidates:
        target = unresolved.resolve()
        in_allowed_roots = not roots or within_root is None or any(within_root(target, root) for root in roots)
        if not in_allowed_roots:
            continue
        saw_allowed_candidate = True
        if target.exists():
            return target

    if saw_allowed_candidate or prefer_missing_not_found:
        raise HTTPException(status_code=404, detail=f"{label} does not exist")
    if roots and within_root is not None:
        raise HTTPException(status_code=400, detail=f"{label} is outside controlled roots")
    raise HTTPException(status_code=404, detail=f"{label} does not exist")


def _ensure_path_within_roots(
    target: Path,
    *,
    label: str,
    allowed_roots: Sequence[Path] | None,
    within_root: Callable[[Path, Path], bool] | None,
) -> None:
    if not allowed_roots or within_root is None:
        return
    if not any(within_root(target, root) for root in allowed_roots):
        raise HTTPException(status_code=400, detail=f"{label} is outside controlled roots")


def resolve_manifest_path(
    store: JobStore,
    analyze_job_id: str | None,
    manifest_path: str | None,
    *,
    allowed_roots: Sequence[Path] | None = None,
    within_root: Callable[[Path, Path], bool] | None = None,
) -> Path:
    if manifest_path:
        return _resolve_allowed_existing_path(
            manifest_path,
            label="manifest_path",
            allowed_roots=allowed_roots,
            within_root=within_root,
        )
    if not analyze_job_id:
        raise HTTPException(status_code=400, detail="analyze_job_id or manifest_path is required")
    source = store.get(analyze_job_id)
    if source is None:
        raise HTTPException(status_code=404, detail="analyze job not found")
    manifest = str(source.summary.get("manifest_path", "") or source.payload.get("manifest_path", "")).strip()
    if not manifest:
        raise HTTPException(status_code=409, detail="analyze job has no manifest output")
    return _resolve_allowed_existing_path(
        manifest,
        label="manifest output",
        allowed_roots=allowed_roots,
        within_root=within_root,
        prefer_missing_not_found=True,
    )


def ensure_controlled_directory(
    path: Path,
    repo_root: Path,
    web_upload_root: Path,
    within_root: Callable[[Path, Path], bool],
) -> None:
    controlled_roots = [repo_root / "data", web_upload_root]
    if not any(within_root(path, root) for root in controlled_roots):
        raise HTTPException(status_code=400, detail="input directory is outside controlled roots")
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail="input directory must exist")


def validate_manifest_for_rollback(manifest_path: Path, read_manifest_rows: Callable[[Path], List[Dict[str, Any]]]) -> None:
    try:
        rows = read_manifest_rows(manifest_path)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"manifest validation failed: {exc}") from exc
    if not rows:
        raise HTTPException(status_code=409, detail="manifest is empty")
    valid = 0
    for row in rows:
        run_id = str(row.get("run_id", "") or "").strip()
        src = str(row.get("path", "") or "").strip()
        moved = str(row.get("new_path", "") or "").strip()
        if run_id and src and moved:
            valid += 1
    if valid == 0:
        raise HTTPException(status_code=409, detail="manifest lacks rollback-ready rows (run_id/path/new_path)")


def overlay_default(now_iso: Callable[[], str], job_id: str) -> Dict[str, Any]:
    return {"job_id": job_id, "updated_at": now_iso(), "rows": {}}


def load_overlay(
    read_json_file: Callable[[Path, Any], Any],
    now_iso: Callable[[], str],
    overlay_path: Path,
    job_id: str,
) -> Dict[str, Any]:
    payload = read_json_file(overlay_path, overlay_default(now_iso, job_id))
    if not isinstance(payload, dict):
        payload = overlay_default(now_iso, job_id)
    payload.setdefault("job_id", job_id)
    payload.setdefault("rows", {})
    if not isinstance(payload.get("rows"), dict):
        payload["rows"] = {}
    payload.setdefault("updated_at", now_iso())
    return payload


def save_overlay(
    write_json_atomic: JsonAtomicWriter,
    now_iso: Callable[[], str],
    overlay_path: Path,
    job_id: str,
    rows: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    payload = {"job_id": job_id, "updated_at": now_iso(), "rows": rows}
    write_json_atomic(overlay_path, payload, root=overlay_path.parent)
    return payload


def _row_identity_candidates(row: Dict[str, Any], index: int) -> List[str]:
    candidates = [str(index)]
    for key in ("row_id", "hash8", "sha1", "path", "new_path"):
        value = str(row.get(key, "") or "").strip()
        if value:
            candidates.append(value)
    return candidates


def coerce_row_index(row_id: str, rows: Sequence[Dict[str, Any]] | int) -> int:
    if isinstance(rows, int):
        row_count = rows
        try:
            index = int(row_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="row_id must be an integer index") from exc
        if index < 0 or index >= row_count:
            raise HTTPException(status_code=404, detail="row not found")
        return index

    row_count = len(rows)
    if row_count == 0:
        raise HTTPException(status_code=404, detail="row not found")
    try:
        index = int(row_id)
        if 0 <= index < row_count:
            return index
    except ValueError:
        pass
    normalized = str(row_id).strip()
    for index, row in enumerate(rows):
        if normalized in _row_identity_candidates(row, index):
            return index
    raise HTTPException(status_code=404, detail="row not found")


def apply_overlay_rows(base_rows: Sequence[Dict[str, Any]], overlay_rows: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    resolved: List[Dict[str, Any]] = [dict(row) for row in base_rows]
    for key, patch in overlay_rows.items():
        try:
            index = int(key)
        except ValueError:
            continue
        if index < 0 or index >= len(resolved):
            continue
        if not isinstance(patch, dict):
            continue
        merged = dict(resolved[index])
        for patch_key, value in patch.items():
            merged[patch_key] = value
        resolved[index] = merged
    return resolved


def detect_manifest_conflicts(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bucket: Dict[str, List[str]] = {}
    for idx, row in enumerate(rows):
        candidate = str(row.get("new_path", "") or "").strip()
        if not candidate:
            continue
        bucket.setdefault(candidate, []).append(str(idx))
    conflicts: List[Dict[str, Any]] = []
    for target, row_ids in bucket.items():
        if len(row_ids) > 1:
            for row_id in row_ids:
                row = rows[int(row_id)]
                conflicts.append(
                    {
                        "id": f"duplicate_path:{row_id}",
                        "row_id": row_id,
                        "type": "duplicate_path",
                        "severity": "warning",
                        "source_path": str(row.get("path", "") or ""),
                        "target_path": target,
                        "reason": f"Duplicate target path: {len(row_ids)} rows point to the same destination",
                        "suggested_target": "",
                        "status": "open",
                        "row_ids": row_ids,
                        "count": len(row_ids),
                    }
                )
    conflicts.sort(key=lambda item: (str(item["target_path"]), str(item["row_id"])))
    return conflicts


def build_preview_payload(row: Dict[str, Any], row_id: str) -> Dict[str, Any]:
    ai_payload = row.get("ai")
    ai = ai_payload if isinstance(ai_payload, dict) else {}
    tags = ai.get("tags")
    tag_values = [str(item).strip() for item in tags] if isinstance(tags, list) else []
    summary_parts = [
        str(ai.get("title", "")).strip(),
        str(ai.get("notes", "")).strip(),
        ", ".join(item for item in tag_values if item),
    ]
    summary = " | ".join(part for part in summary_parts if part)
    extra: Dict[str, Any] = {}
    for key in ("path", "new_path", "status", "error_code", "media_type", "sha1", "hash8"):
        value = row.get(key)
        if value not in {None, ""}:
            extra[key] = str(value)
    return {
        "row_id": row_id,
        "media_type": str(row.get("media_type", "unknown") or "unknown"),
        "summary": summary or str(row.get("path", "")).strip(),
        "duration_s": row.get("duration_s"),
        "pages": row.get("pages"),
        "mime": row.get("mime"),
        "extra": extra,
    }


def get_manifest_path_for_job(record: JobRecord) -> Path:
    candidate = str(record.summary.get("manifest_path", "") or record.payload.get("manifest_path", "")).strip()
    if not candidate:
        raise HTTPException(status_code=409, detail="job has no manifest output")
    target = Path(candidate).expanduser().resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail="manifest file is missing")
    return target


def sse(event: str, payload: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def read_preference_items(read_json_file: Callable[[Path, Any], Any], path: Path) -> Dict[str, Dict[str, Any]]:
    payload = read_json_file(path, {"items": {}})
    if not isinstance(payload, dict):
        return {}
    items = payload.get("items", {})
    if not isinstance(items, dict):
        return {}
    normalized: Dict[str, Dict[str, Any]] = {}
    for key, value in items.items():
        if isinstance(key, str) and isinstance(value, dict):
            normalized[key] = dict(value)
    return normalized


def write_preference_items(
    write_json_atomic: JsonAtomicWriter,
    now_iso: Callable[[], str],
    path: Path,
    items: Dict[str, Dict[str, Any]],
) -> None:
    write_json_atomic(path, {"updated_at": now_iso(), "items": items}, root=path.parent)
