from __future__ import annotations


def _is_bool(value) -> bool:
    return isinstance(value, bool)


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return (isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float)


def _is_str_or_str_list(value) -> bool:
    if isinstance(value, str):
        return True
    if isinstance(value, (list, tuple)):
        return all(isinstance(item, str) for item in value)
    return False


_ALLOWED_CONFIG = {
    "global": {
        "log_level",
        "log_json",
        "run_id",
        "generator_version",
        "active_strategy_pack_id",
        "trace_id",
        "request_id",
        "session_id",
        "user_id",
    },
    "analyze": {
        "input",
        "manifest",
        "csv",
        "report",
        "model",
        "categories",
        "durability",
        "fsync_interval",
        "inline_max_mb",
        "resize_max_side",
        "max_retries",
        "retry_base_s",
        "retry_max_s",
        "ai_timeout_s",
        "subprocess_timeout_s",
        "audio_segment_threshold",
        "audio_segment_seconds",
        "audio_segment_count",
        "audio_transcript_max_chars",
        "doc_text_max_chars",
        "max_file_mb",
        "max_files",
        "max_total_mb",
        "workers",
        "offline",
        "sleep",
        "chunk_size",
    },
    "apply": {
        "manifest",
        "output",
        "categories",
        "input_root",
        "dry_run",
        "out_manifest",
        "report",
        "verify_sha1",
        "durability",
        "fsync_interval",
        "dedupe",
        "resume",
        "retry_errors",
        "trust_manifest_input_root",
        "manifest_input_root_allowlist",
        "rollback_manifest",
        "chunk_size",
        "crash_inject",
    },
    "rollback": {
        "manifest",
        "dry_run",
        "overwrite",
        "allowed_root",
        "strict_integrity",
    },
    "report": {
        "manifest",
        "out",
        "validate",
        "chunk_size",
    },
}

_CONFIG_TYPE_RULES = {
    "global": {
        "log_level": str,
        "log_json": _is_bool,
        "run_id": str,
        "generator_version": str,
        "active_strategy_pack_id": str,
        "trace_id": str,
        "request_id": str,
        "session_id": str,
        "user_id": str,
    },
    "analyze": {
        "input": str,
        "manifest": str,
        "csv": str,
        "report": str,
        "model": str,
        "categories": _is_str_or_str_list,
        "durability": str,
        "fsync_interval": _is_int,
        "inline_max_mb": _is_number,
        "resize_max_side": _is_int,
        "max_retries": _is_int,
        "retry_base_s": _is_number,
        "retry_max_s": _is_number,
        "ai_timeout_s": _is_number,
        "subprocess_timeout_s": _is_number,
        "audio_segment_threshold": _is_number,
        "audio_segment_seconds": _is_number,
        "audio_segment_count": _is_int,
        "audio_transcript_max_chars": _is_int,
        "doc_text_max_chars": _is_int,
        "max_file_mb": _is_number,
        "max_files": _is_int,
        "max_total_mb": _is_number,
        "workers": _is_int,
        "offline": _is_bool,
        "sleep": _is_number,
        "chunk_size": _is_int,
    },
    "apply": {
        "manifest": str,
        "output": str,
        "categories": _is_str_or_str_list,
        "input_root": str,
        "dry_run": _is_bool,
        "out_manifest": str,
        "report": str,
        "verify_sha1": _is_bool,
        "durability": str,
        "fsync_interval": _is_int,
        "dedupe": _is_bool,
        "resume": _is_bool,
        "retry_errors": _is_bool,
        "trust_manifest_input_root": _is_bool,
        "manifest_input_root_allowlist": str,
        "rollback_manifest": str,
        "chunk_size": _is_int,
        "crash_inject": str,
    },
    "rollback": {
        "manifest": str,
        "dry_run": _is_bool,
        "overwrite": _is_bool,
        "allowed_root": str,
        "strict_integrity": _is_bool,
    },
    "report": {
        "manifest": str,
        "out": str,
        "validate": _is_bool,
        "chunk_size": _is_int,
    },
}
