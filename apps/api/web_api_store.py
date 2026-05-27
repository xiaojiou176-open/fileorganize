# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List

from apps.api.web_api_core import _now_iso, _read_json_file, _safe_float_progress, _write_json_atomic
from apps.api.web_api_models import TERMINAL_JOB_STATUSES, JobEvent, JobKind, JobRecord, JobStatus


class JobStore:
    def __init__(self, job_root: Path) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, JobRecord] = {}
        self._job_root = job_root
        self._index_path = self._job_root / "index.json"
        self._job_root.mkdir(parents=True, exist_ok=True)
        self._load_persisted_jobs()

    @property
    def index_path(self) -> Path:
        return self._index_path

    def job_dir(self, job_id: str) -> Path:
        return self._job_root / job_id

    def job_file(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "job.json"

    def events_file(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "events.jsonl"

    def overlay_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "manifest_overlay.json"

    def create(self, kind: JobKind, payload: Dict[str, Any], retry_of: str | None = None) -> JobRecord:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        record = JobRecord(
            id=job_id,
            kind=kind,
            status="queued",
            phase_label="queued",
            progress=0.0,
            created_at=now,
            payload=dict(payload),
            retry_of=retry_of,
        )
        with self._lock:
            self._jobs[job_id] = record
            self.job_dir(job_id).mkdir(parents=True, exist_ok=True)
            self.events_file(job_id).touch(exist_ok=True)
            self._append_event_locked(
                record,
                level="info",
                message="job_created",
                fields={"kind": kind, "retry_of": retry_of or ""},
            )
            self._write_job_locked(record)
            self._write_index_locked()
        return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> List[JobRecord]:
        with self._lock:
            items = list(self._jobs.values())
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items

    def list_history(self) -> List[JobRecord]:
        return self.list()

    def snapshot(self, job_id: str) -> Dict[str, Any] | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            return self._record_view_dict(record)

    def mark_running(self, job_id: str) -> bool:
        now = _now_iso()
        with self._lock:
            record = self._jobs[job_id]
            if record.status == "cancelled":
                return False
            if record.status in TERMINAL_JOB_STATUSES:
                return False
            record.started_at = record.started_at or now
            record.progress = max(record.progress, 0.05)
            if record.cancel_requested_at:
                record.status = "cancelling"
                record.phase_label = "cancelling"
                self._append_event_locked(record, "warn", "job_cancelling", {"reason": "cancel_requested_before_start"})
            else:
                record.status = "running"
                record.phase_label = "running"
                self._append_event_locked(record, "info", "job_started", {})
            self._write_job_locked(record)
            self._write_index_locked()
        return True

    def mark_succeeded(self, job_id: str, summary: Dict[str, Any]) -> None:
        now = _now_iso()
        with self._lock:
            record = self._jobs[job_id]
            record.status = "succeeded"
            record.phase_label = "succeeded"
            record.progress = 1.0
            record.finished_at = now
            record.summary = dict(summary)
            self._append_event_locked(record, "info", "job_succeeded", {"summary": summary})
            self._write_job_locked(record)
            self._write_index_locked()

    def mark_failed(self, job_id: str, error: str) -> None:
        now = _now_iso()
        with self._lock:
            record = self._jobs[job_id]
            record.status = "failed"
            record.phase_label = "failed"
            record.progress = max(record.progress, 0.1)
            record.finished_at = now
            record.latest_error = error
            self._append_event_locked(record, "error", "job_failed", {"error": error})
            self._write_job_locked(record)
            self._write_index_locked()

    def mark_cancelled(self, job_id: str, reason: str) -> None:
        now = _now_iso()
        with self._lock:
            record = self._jobs[job_id]
            if record.status == "cancelled":
                return
            record.status = "cancelled"
            record.phase_label = "cancelled"
            record.progress = max(record.progress, 0.1)
            record.finished_at = now
            record.latest_error = reason
            record.cancel_requested_at = record.cancel_requested_at or now
            self._append_event_locked(record, "warn", "job_cancelled", {"reason": reason})
            self._write_job_locked(record)
            self._write_index_locked()

    def request_cancel(self, job_id: str) -> JobRecord | None:
        now = _now_iso()
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            if record.status in TERMINAL_JOB_STATUSES:
                return record
            record.cancel_requested_at = record.cancel_requested_at or now
            if record.status == "queued":
                record.status = "cancelled"
                record.phase_label = "cancelled"
                record.finished_at = now
                self._append_event_locked(record, "warn", "job_cancelled", {"reason": "cancelled_while_queued"})
            elif record.status in {"running", "cancelling"}:
                record.status = "cancelling"
                record.phase_label = "cancelling"
                self._append_event_locked(record, "warn", "job_cancelling", {"reason": "cancel_requested"})
            self._write_job_locked(record)
            self._write_index_locked()
            return record

    def update_phase(self, job_id: str, phase_label: str, progress: float) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.phase_label = phase_label
            record.progress = _safe_float_progress(progress)

    def add_event(self, job_id: str, level: str, message: str, **fields: Any) -> None:
        with self._lock:
            record = self._jobs[job_id]
            self._append_event_locked(record, level=level, message=message, fields=fields)

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            record = self._jobs[job_id]
            return record.cancel_requested_at is not None

    def event_count(self, job_id: str) -> int:
        with self._lock:
            record = self._jobs[job_id]
            return len(record.events)

    def events_since(self, job_id: str, cursor: int) -> tuple[List[Dict[str, Any]], int, JobStatus]:
        with self._lock:
            record = self._jobs[job_id]
            sliced = record.events[cursor:]
            payload = [self._event_dict(event) for event in sliced]
            return payload, cursor + len(payload), record.status

    def has_dry_run_success(self, manifest_path: Path) -> bool:
        target = manifest_path.resolve()
        with self._lock:
            for record in self._jobs.values():
                if record.kind != "apply" or record.status != "succeeded":
                    continue
                if not bool(record.summary.get("dry_run")):
                    continue
                source_manifest = str(record.summary.get("source_manifest_path", "") or "").strip()
                if not source_manifest:
                    continue
                try:
                    if Path(source_manifest).expanduser().resolve() == target:
                        return True
                except Exception:
                    continue
        return False

    def _append_event_locked(self, record: JobRecord, level: str, message: str, fields: Dict[str, Any]) -> None:
        event = JobEvent(
            seq=len(record.events) + 1,
            timestamp=_now_iso(),
            level=level,
            message=message,
            fields=dict(fields),
        )
        record.events.append(event)
        with self.events_file(record.id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(self._event_dict(event), ensure_ascii=False) + "\n")

    def _record_dict(self, record: JobRecord) -> Dict[str, Any]:
        return {
            "id": record.id,
            "kind": record.kind,
            "status": record.status,
            "phase_label": record.phase_label,
            "progress": record.progress,
            "created_at": record.created_at,
            "started_at": record.started_at,
            "finished_at": record.finished_at,
            "retry_of": record.retry_of,
            "cancel_requested_at": record.cancel_requested_at,
            "summary": record.summary,
            "latest_error": record.latest_error,
            "payload": record.payload,
        }

    def _record_view_dict(self, record: JobRecord) -> Dict[str, Any]:
        return {
            "id": record.id,
            "kind": record.kind,
            "status": record.status,
            "phase_label": record.phase_label,
            "phase": record.phase_label,
            "progress": record.progress,
            "started_at": record.started_at,
            "finished_at": record.finished_at,
            "retry_of": record.retry_of,
            "cancel_requested_at": record.cancel_requested_at,
            "summary": record.summary,
            "latest_error": record.latest_error,
        }

    @staticmethod
    def _event_dict(event: JobEvent) -> Dict[str, Any]:
        return {
            "seq": event.seq,
            "timestamp": event.timestamp,
            "level": event.level,
            "message": event.message,
            "fields": event.fields,
        }

    def _write_job_locked(self, record: JobRecord) -> None:
        _write_json_atomic(
            self.job_file(record.id),
            self._record_dict(record),
            root=self.job_dir(record.id),
        )

    def _write_index_locked(self) -> None:
        jobs = [
            {
                "id": record.id,
                "kind": record.kind,
                "status": record.status,
                "phase_label": record.phase_label,
                "progress": record.progress,
                "created_at": record.created_at,
                "started_at": record.started_at,
                "finished_at": record.finished_at,
                "retry_of": record.retry_of,
                "cancel_requested_at": record.cancel_requested_at,
            }
            for record in sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
        ]
        _write_json_atomic(
            self._index_path,
            {"updated_at": _now_iso(), "jobs": jobs},
            root=self._job_root,
        )

    def _load_persisted_jobs(self) -> None:
        with self._lock:
            candidate_ids: List[str] = []
            index_payload = _read_json_file(self._index_path, default={})
            if isinstance(index_payload, dict):
                jobs_list = index_payload.get("jobs", [])
                if isinstance(jobs_list, list):
                    for item in jobs_list:
                        if isinstance(item, dict):
                            job_id = str(item.get("id", "") or "").strip()
                            if job_id:
                                candidate_ids.append(job_id)
            if not candidate_ids:
                for child in self._job_root.iterdir():
                    if child.is_dir() and (child / "job.json").exists():
                        candidate_ids.append(child.name)
            seen = set()
            for job_id in candidate_ids:
                if job_id in seen:
                    continue
                seen.add(job_id)
                job_file = self.job_file(job_id)
                if not job_file.exists():
                    continue
                try:
                    payload = json.loads(job_file.read_text(encoding="utf-8"))
                except Exception:
                    continue
                kind = str(payload.get("kind", "") or "").strip()
                status = str(payload.get("status", "") or "").strip()
                if kind not in {"analyze", "apply", "rollback"}:
                    continue
                if status not in {"queued", "running", "cancelling", "cancelled", "succeeded", "failed"}:
                    status = "failed"
                record = JobRecord(
                    id=job_id,
                    kind=kind,  # type: ignore[arg-type]
                    status=status,  # type: ignore[arg-type]
                    phase_label=str(payload.get("phase_label", "queued") or "queued"),
                    progress=_safe_float_progress(float(payload.get("progress", 0.0) or 0.0)),
                    created_at=str(payload.get("created_at", "") or _now_iso()),
                    started_at=payload.get("started_at"),
                    finished_at=payload.get("finished_at"),
                    retry_of=payload.get("retry_of"),
                    cancel_requested_at=payload.get("cancel_requested_at"),
                    summary=dict(payload.get("summary", {}) or {}),
                    latest_error=payload.get("latest_error"),
                    payload=dict(payload.get("payload", {}) or {}),
                    events=[],
                )
                events_path = self.events_file(job_id)
                if events_path.exists():
                    lines = events_path.read_text(encoding="utf-8").splitlines()
                    for idx, line in enumerate(lines, start=1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            event_payload = json.loads(line)
                        except Exception:
                            continue
                        record.events.append(
                            JobEvent(
                                seq=int(event_payload.get("seq", idx) or idx),
                                timestamp=str(event_payload.get("timestamp", _now_iso())),
                                level=str(event_payload.get("level", "info") or "info"),
                                message=str(event_payload.get("message", "")),
                                fields=dict(event_payload.get("fields", {}) or {}),
                            )
                        )
                self._jobs[job_id] = record
