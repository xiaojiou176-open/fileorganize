# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field

JobKind = Literal["analyze", "apply", "rollback"]
JobStatus = Literal["queued", "running", "cancelling", "cancelled", "succeeded", "failed"]

TERMINAL_JOB_STATUSES = {"cancelled", "succeeded", "failed"}


@dataclass
class JobEvent:
    seq: int
    timestamp: str
    level: str
    message: str
    fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobRecord:
    id: str
    kind: JobKind
    status: JobStatus
    phase_label: str
    progress: float
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    retry_of: str | None = None
    cancel_requested_at: str | None = None
    summary: Dict[str, Any] = field(default_factory=dict)
    latest_error: str | None = None
    payload: Dict[str, Any] = field(default_factory=dict)
    events: List[JobEvent] = field(default_factory=list)


class JobView(BaseModel):
    id: str
    kind: JobKind
    status: JobStatus
    phase_label: str
    phase: str
    progress: float
    started_at: str | None = None
    finished_at: str | None = None
    retry_of: str | None = None
    cancel_requested_at: str | None = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    latest_error: str | None = None

    model_config = ConfigDict(extra="forbid")


class AnalyzeJsonRequest(BaseModel):
    input_mode: Literal["directory", "upload"] = "directory"
    input_directory: str | None = None
    strategy_pack_id: str | None = None
    watch_source_id: str | None = None
    trigger_source: Literal["manual", "inbox"] = "manual"
    model: str | None = None
    categories: str | None = None
    workers: int | None = None
    max_files: int | None = None
    max_total_mb: float | None = None
    max_file_mb: float | None = None
    offline: bool = False

    model_config = ConfigDict(extra="forbid")


class InboxAnalyzeRequest(BaseModel):
    watch_source_id: str = Field(min_length=1)
    batch_id: str | None = None
    strategy_pack_id: str | None = None
    model: str | None = None
    categories: str | None = None
    workers: int | None = Field(default=None, ge=1)
    max_files: int | None = Field(default=None, ge=0)
    max_total_mb: float | None = Field(default=None, ge=0)
    max_file_mb: float | None = Field(default=None, ge=0)
    offline: bool = False

    model_config = ConfigDict(extra="forbid")


class ApplyRequest(BaseModel):
    analyze_job_id: str | None = None
    manifest_path: str | None = None
    output_root: str | None = None
    execute: bool = False

    model_config = ConfigDict(extra="forbid")


class RollbackRequest(BaseModel):
    analyze_job_id: str | None = None
    manifest_path: str | None = None
    execute: bool = False
    source_job_id: str | None = None
    allowed_root: str | None = None
    strict_integrity: bool = True
    audit_reason: str | None = None

    model_config = ConfigDict(extra="forbid")


class ManifestRowPatchRequest(BaseModel):
    patch: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ManifestBatchOperation(BaseModel):
    row_id: str
    patch: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ManifestBatchRequest(BaseModel):
    operations: List[ManifestBatchOperation] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ManifestConflictResolution(BaseModel):
    row_id: str
    new_path: str

    model_config = ConfigDict(extra="forbid")


class ManifestConflictResolveRequest(BaseModel):
    resolutions: List[ManifestConflictResolution] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class PreferenceUpsertRequest(BaseModel):
    key: str = Field(min_length=1)
    value: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ReviewRuleConditionRequest(BaseModel):
    query: str = ""
    statuses: List[str] = Field(default_factory=list)
    media_types: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    review_buckets: List[str] = Field(default_factory=list)
    min_confidence: float | None = Field(default=None, ge=0)
    max_confidence: float | None = Field(default=None, ge=0)
    has_conflict: bool | None = None
    ignore_state: bool | None = None

    model_config = ConfigDict(extra="forbid")


class ReviewRuleActionRequest(BaseModel):
    set_category: str | None = None
    set_ignore: bool | None = None
    target_pattern: str | None = None

    model_config = ConfigDict(extra="forbid")


class ReviewRuleUpsertRequest(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1)
    scope: Literal["manifest", "report", "jobs"] = "manifest"
    description: str = ""
    version: int = Field(default=1, ge=1)
    conditions: ReviewRuleConditionRequest = Field(default_factory=ReviewRuleConditionRequest)
    actions: ReviewRuleActionRequest = Field(default_factory=ReviewRuleActionRequest)

    model_config = ConfigDict(extra="forbid")


class ReviewRuleApplyRequest(BaseModel):
    rule_id: str | None = None
    rule: ReviewRuleUpsertRequest | None = None

    model_config = ConfigDict(extra="forbid")


class ReviewRuleFromExamplesRequest(BaseModel):
    row_ids: List[str] = Field(default_factory=list, min_length=2, max_length=5)
    name: str | None = None

    model_config = ConfigDict(extra="forbid")


class ReviewQueueBatchTriageRequest(BaseModel):
    row_ids: List[str] = Field(default_factory=list, min_length=1, max_length=200)
    set_category: str | None = None
    set_ignore: bool | None = None

    model_config = ConfigDict(extra="forbid")


class WatchSourceUpsertRequest(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1)
    input_root: str = Field(min_length=1)
    enabled: bool = True
    strategy_pack_id: str = ""

    model_config = ConfigDict(extra="forbid")


class RuntimeSettingsUpdateRequest(BaseModel):
    api_key: str | None = None
    clear_api_key: bool = False
    model: str | None = None
    active_strategy_pack_id: str | None = None
    input_root: str | None = None
    output_root: str | None = None
    workers: int | None = Field(default=None, ge=1)
    categories: str | None = None
    max_files: int | None = Field(default=None, ge=0)
    max_total_mb: float | None = Field(default=None, ge=0)
    max_file_mb: float | None = Field(default=None, ge=0)
    create_missing_dirs: bool = True

    model_config = ConfigDict(extra="forbid")


class RuntimeAnalyzeDefaultsView(BaseModel):
    workers: int
    categories: List[str] = Field(default_factory=list)
    max_files: int
    max_total_mb: float
    max_file_mb: float

    model_config = ConfigDict(extra="forbid")


class RuntimeSettingsView(BaseModel):
    workspace_root: str
    runtime_env_path: str
    input_root: str
    output_root: str
    allowed_root: str
    manifest_root: str
    artifact_root: str
    has_api_key: bool
    api_key_masked: str = ""
    api_key_source: Literal["env", "runtime_env", "missing"]
    api_key_status: Literal["configured", "missing", "placeholder"]
    model: str
    model_source: Literal["env", "runtime_env", "default"]
    active_strategy_pack_id: str = ""
    input_root_exists: bool
    output_root_exists: bool
    ready: bool
    analyze_defaults: RuntimeAnalyzeDefaultsView
    missing: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    checked_at: str

    model_config = ConfigDict(extra="forbid")
