import type {
  CollectionSummary,
  InboxBatch,
  InboxAnalyzeResponse,
  InputMode,
  Job,
  JobEvent,
  JobsQuery,
  JobSummary,
  LearnedRule,
  LearnedSuggestion,
  ManifestConflict,
  ManifestRow,
  ManifestRowPatch,
  NamingTemplate,
  PreviewPayload,
  ReviewCopilotSummary,
  ReviewQueueBatchTriageMeta,
  ReviewQueueSummary,
  RulePreview,
  ReviewRuleDraftResponse,
  ReviewRule,
  SavedView,
  StrategyPack,
  WatchSource,
} from './types'
import { normalizeJobStatus } from './job-status'
import { apiContract, API_ROOT } from '../../../../contracts/api/generated/webui/client'

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }

type StreamState = 'connecting' | 'open' | 'error' | 'unsupported' | 'closed'
const JOBS_POLL_INTERVAL_MS = 1200

interface AnalyzeOptions {
  inputMode: InputMode
  inputDirectory?: string
  files?: File[]
  model?: string
  categories?: string
  workers?: number
  maxFiles?: number
  maxTotalMb?: number
  maxFileMb?: number
  offline?: boolean
}

interface ApplyOptions {
  analyzeJobId?: string
  manifestPath?: string
  outputRoot?: string
  execute?: boolean
}

export interface RollbackOptions {
  analyzeJobId?: string
  manifestPath?: string
  execute?: boolean
  sourceJobId?: string
  allowedRoot?: string
  strictIntegrity?: boolean
  auditReason?: string
}

interface EventStreamHandlers {
  onMessage: (payload: unknown) => void
  onState?: (state: StreamState) => void
}

interface PreviewRequestOptions {
  signal?: AbortSignal
  throwOnError?: boolean
}

export interface ReviewQueuePayload {
  job: Job | null
  job_id: string
  manifest_path: string
  overlay_path: string
  overlay_updated_at?: string
  summary: ReviewQueueSummary
  copilot_summary?: ReviewCopilotSummary
  collections: CollectionSummary[]
  rows: ManifestRow[]
  returned: number
}

interface PreferenceItem {
  key: string
  value: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface RuntimeAnalyzeDefaults {
  workers: number
  categories: string[]
  max_files: number
  max_total_mb: number
  max_file_mb: number
}

export interface RuntimeSettings {
  workspace_root: string
  runtime_env_path: string
  input_root: string
  output_root: string
  allowed_root: string
  manifest_root: string
  artifact_root: string
  has_api_key: boolean
  api_key_masked: string
  api_key_source: 'env' | 'runtime_env' | 'missing' // pragma: allowlist secret
  api_key_status: 'configured' | 'missing' | 'placeholder' // pragma: allowlist secret
  model: string
  model_source: 'env' | 'runtime_env' | 'default'
  active_strategy_pack_id: string
  input_root_exists: boolean
  output_root_exists: boolean
  ready: boolean
  analyze_defaults: RuntimeAnalyzeDefaults
  missing: string[]
  warnings: string[]
  checked_at: string
}

export interface RuntimeSettingsUpdateInput {
  apiKey?: string
  clearApiKey?: boolean
  model?: string
  activeStrategyPackId?: string
  inputRoot?: string
  outputRoot?: string
  workers?: number
  categories?: string
  maxFiles?: number
  maxTotalMb?: number
  maxFileMb?: number
  createMissingDirs?: boolean
}

class ApiRequestError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
  }
}

function isRecord(value: unknown): value is Record<string, JsonValue> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isJsonRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function buildQuery<T extends object>(query?: T): string {
  if (!query) {
    return ''
  }
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) {
      continue
    }
    const normalized = typeof value === 'string' ? value.trim() : String(value)
    if (normalized.length > 0) {
      params.set(key, normalized)
    }
  }
  const encoded = params.toString()
  return encoded.length > 0 ? `?${encoded}` : ''
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, init)
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`.trim()
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) {
        detail = payload.detail
      }
    } catch {
      // ignore JSON parse failures and keep default detail
    }
    throw new ApiRequestError(response.status, detail)
  }
  return (await response.json()) as T
}

function contractPath(path: string): string {
  return path.startsWith(API_ROOT) ? path.slice(API_ROOT.length) : path
}

function mapSummary(value: unknown): JobSummary | undefined {
  if (!isRecord(value)) {
    return undefined
  }
  return {
    total: Number(value.total ?? 0),
    with_error: Number(value.with_error ?? 0),
    by_media_type: isRecord(value.by_media_type) ? (value.by_media_type as Record<string, number>) : {},
    by_category: isRecord(value.by_category) ? (value.by_category as Record<string, number>) : {},
    by_status: isRecord(value.by_status) ? (value.by_status as Record<string, number>) : {},
    error_codes: isRecord(value.error_codes) ? (value.error_codes as Record<string, number>) : {},
    by_review_bucket: isRecord(value.by_review_bucket) ? (value.by_review_bucket as Record<string, number>) : {},
    collection_count: typeof value.collection_count === 'number' ? value.collection_count : undefined,
    collection_ids: Array.isArray(value.collection_ids) ? value.collection_ids.map((item) => String(item)) : undefined,
    manifest_path: typeof value.manifest_path === 'string' ? value.manifest_path : undefined,
    report_path: typeof value.report_path === 'string' ? value.report_path : undefined,
    rollback_manifest_path: typeof value.rollback_manifest_path === 'string' ? value.rollback_manifest_path : undefined,
    input_mode: value.input_mode === 'directory' || value.input_mode === 'upload' ? value.input_mode : undefined,
    input_root: typeof value.input_root === 'string' ? value.input_root : undefined,
    output_root: typeof value.output_root === 'string' ? value.output_root : undefined,
    dry_run: typeof value.dry_run === 'boolean' ? value.dry_run : undefined,
    allowed_root: typeof value.allowed_root === 'string' ? value.allowed_root : undefined,
  }
}

function mapJob(raw: unknown): Job {
  if (!isRecord(raw)) {
    throw new Error('Invalid job payload')
  }

  const summary = mapSummary(raw.summary)
  const manifestPath = typeof raw.manifest_path === 'string' ? raw.manifest_path : summary?.manifest_path
  const reportPath = typeof raw.report_path === 'string' ? raw.report_path : summary?.report_path
  const rollbackManifestPath =
    typeof raw.rollback_manifest_path === 'string' ? raw.rollback_manifest_path : summary?.rollback_manifest_path

  return {
    id: String(raw.id ?? ''),
    kind: (raw.kind as Job['kind']) ?? 'analyze',
    status: normalizeJobStatus(raw.status),
    phase: String(raw.phase ?? 'queued'),
    progress: Number(raw.progress ?? 0),
    started_at: typeof raw.started_at === 'string' ? raw.started_at : undefined,
    finished_at: typeof raw.finished_at === 'string' ? raw.finished_at : undefined,
    retry_of: typeof raw.retry_of === 'string' ? raw.retry_of : undefined,
    cancel_requested_at: typeof raw.cancel_requested_at === 'string' ? raw.cancel_requested_at : undefined,
    summary,
    latest_error: typeof raw.latest_error === 'string' ? raw.latest_error : undefined,
    manifest_path: manifestPath,
    report_path: reportPath,
    rollback_manifest_path: rollbackManifestPath,
    dry_run_verified: summary?.dry_run === true,
    strict_integrity_ready: Boolean(summary?.allowed_root || raw.strict_integrity_ready),
  }
}

function mapEvent(raw: unknown, index: number): JobEvent {
  if (!isRecord(raw)) {
    return {
      timestamp: new Date().toISOString(),
      level: 'info',
      message: `event-${index}`,
    }
  }

  return {
    id: typeof raw.id === 'string' ? raw.id : undefined,
    timestamp: typeof raw.timestamp === 'string' ? raw.timestamp : new Date().toISOString(),
    level: typeof raw.level === 'string' ? raw.level : 'info',
    message: typeof raw.message === 'string' ? raw.message : `event-${index}`,
    fields: isRecord(raw.fields) ? raw.fields : undefined,
  }
}

function mapManifestRow(raw: unknown, index: number): ManifestRow {
  if (!isRecord(raw)) {
    return {
      id: `row-${index}`,
      file_name: `row-${index}`,
      media_type: 'unknown',
      category: '其他',
      title: '未命名条目',
      tags: [],
      status: 'pending',
      error_code: '',
      target_path: '',
      target_suggestion: '',
      confidence: 0,
      original_path: '',
      notes: '',
      ignore: false,
      metadata: {},
    }
  }

  const ai = isRecord(raw.ai) ? raw.ai : {}
  const tagsRaw = Array.isArray(ai.tags) ? ai.tags : []
  const tags = tagsRaw.map((item) => String(item)).filter((item) => item.trim().length > 0)
  const metadata = Object.entries(raw)
    .filter(([key]) => !['path', 'new_path', 'status', 'error_code', 'ai', 'dedupe_of', 'ignore', 'row_id'].includes(key))
    .reduce<Record<string, string>>((acc, [key, value]) => {
      if (typeof value === 'string' || typeof value === 'number') {
        acc[key] = String(value)
      }
      return acc
    }, {})

  const originalPath = typeof raw.path === 'string' ? raw.path : ''
  const targetPath = typeof raw.new_path === 'string' ? raw.new_path : ''
  const rowId =
    typeof raw.row_id === 'string' || typeof raw.row_id === 'number'
      ? String(raw.row_id)
      : String(raw.hash8 ?? raw.sha1 ?? raw.path ?? `row-${index}`)

  return {
    id: rowId,
    file_name: originalPath.split('/').at(-1) ?? `row-${index}`,
    media_type: typeof raw.media_type === 'string' ? raw.media_type : 'unknown',
    category: typeof ai.category === 'string' ? ai.category : '其他',
    title: typeof ai.title === 'string' ? ai.title : '未命名条目',
    tags,
    status: typeof raw.status === 'string' ? raw.status : 'pending',
    error_code: typeof raw.error_code === 'string' ? raw.error_code : '',
    target_path: targetPath,
    target_suggestion: typeof raw.target_suggestion === 'string' ? raw.target_suggestion : targetPath,
    dedupe_of: typeof raw.dedupe_of === 'string' ? raw.dedupe_of : undefined,
    confidence: Number(ai.confidence ?? 0),
    original_path: originalPath,
    notes: typeof ai.notes === 'string' ? ai.notes : '',
    ignore: Boolean(raw.ignore),
    review_bucket:
      raw.review_bucket === 'auto_safe' || raw.review_bucket === 'needs_review' || raw.review_bucket === 'conflict' || raw.review_bucket === 'blocked'
        ? raw.review_bucket
        : undefined,
    has_conflict: typeof raw.has_conflict === 'boolean' ? raw.has_conflict : undefined,
    edited: typeof raw.edited === 'boolean' ? raw.edited : undefined,
    collection_id: typeof raw.collection_id === 'string' ? raw.collection_id : undefined,
    collection_title: typeof raw.collection_title === 'string' ? raw.collection_title : undefined,
    collection_reason: typeof raw.collection_reason === 'string' ? raw.collection_reason : undefined,
    collection_confidence: typeof raw.collection_confidence === 'number' ? raw.collection_confidence : undefined,
    collection_kind: typeof raw.collection_kind === 'string' ? raw.collection_kind : undefined,
    collection_next_step: typeof raw.collection_next_step === 'string' ? raw.collection_next_step : undefined,
    learned_suggestions: Array.isArray(raw.learned_suggestions)
      ? (raw.learned_suggestions as unknown[])
          .filter((item): item is Record<string, unknown> => isJsonRecord(item))
          .map((item): LearnedSuggestion => ({
            signal_key: String(item.signal_key ?? ''),
            signal_value: String(item.signal_value ?? ''),
            suggestion_type: String(item.suggestion_type ?? ''),
            suggestion_value: String(item.suggestion_value ?? ''),
            confidence: Number(item.confidence ?? 0),
            count: Number(item.count ?? 0),
            confidence_label:
              item.confidence_label === 'high' || item.confidence_label === 'medium' || item.confidence_label === 'weak'
                ? item.confidence_label
                : 'weak',
            strength:
              item.strength === 'strong' || item.strength === 'medium' || item.strength === 'weak'
                ? item.strength
                : 'weak',
            reuse_scope:
              item.reuse_scope === 'reusable' || item.reuse_scope === 'transient'
                ? item.reuse_scope
                : 'transient',
            source: typeof item.source === 'string' ? item.source : '',
            reason: typeof item.reason === 'string' ? item.reason : '',
            explanation: typeof item.explanation === 'string' ? item.explanation : '',
            scope_reason: typeof item.scope_reason === 'string' ? item.scope_reason : '',
          }))
      : undefined,
    metadata,
  }
}

function mapCopilotSummary(raw: unknown): ReviewCopilotSummary | undefined {
  if (!isJsonRecord(raw)) {
    return undefined
  }
  const normalizeBucket = (value: unknown): 'auto_safe' | 'needs_review' | 'conflict' | 'blocked' =>
    value === 'auto_safe' || value === 'conflict' || value === 'blocked' ? value : 'needs_review'
  return {
    mode: String(raw.mode ?? ''),
    headline: String(raw.headline ?? ''),
    reasons: Array.isArray(raw.reasons)
      ? raw.reasons.filter(isJsonRecord).map((item) => ({
          key: String(item.key ?? ''),
          title: String(item.title ?? ''),
          count: Number(item.count ?? 0),
          detail: String(item.detail ?? ''),
        }))
      : [],
    priorities: Array.isArray(raw.priorities)
      ? raw.priorities.filter(isJsonRecord).map((item) => ({
          row_id: String(item.row_id ?? ''),
          file_name: String(item.file_name ?? ''),
          bucket: normalizeBucket(item.bucket),
          reason: String(item.reason ?? ''),
          suggested_action: String(item.suggested_action ?? ''),
          confidence: Number(item.confidence ?? 0),
        }))
      : [],
    rule_opportunities: Array.isArray(raw.rule_opportunities)
      ? raw.rule_opportunities.filter(isJsonRecord).map((item) => ({
          key: String(item.key ?? ''),
          title: String(item.title ?? ''),
          reason: String(item.reason ?? ''),
          row_ids: Array.isArray(item.row_ids) ? item.row_ids.map((rowId) => String(rowId)) : [],
          suggested_action: String(item.suggested_action ?? ''),
        }))
      : [],
    batch_triage: Array.isArray(raw.batch_triage)
      ? raw.batch_triage.filter(isJsonRecord).map((item) => ({
          id: String(item.id ?? ''),
          kind: item.kind === 'collection' ? 'collection' : 'bucket',
          label: String(item.label ?? ''),
          review_bucket: normalizeBucket(item.review_bucket),
          collection_id: typeof item.collection_id === 'string' ? item.collection_id : undefined,
          count: Number(item.count ?? 0),
          row_ids: Array.isArray(item.row_ids) ? item.row_ids.map((rowId) => String(rowId)) : [],
          reason: String(item.reason ?? ''),
          next_step: String(item.next_step ?? ''),
        }))
      : [],
    guardrails: isJsonRecord(raw.guardrails)
      ? {
          review_only: Boolean(raw.guardrails.review_only),
          draft_only: Boolean(raw.guardrails.draft_only),
          overlay_only: Boolean(raw.guardrails.overlay_only),
          execute_allowed: Boolean(raw.guardrails.execute_allowed),
          auto_apply: Boolean(raw.guardrails.auto_apply),
          allowed_routes: Array.isArray(raw.guardrails.allowed_routes) ? raw.guardrails.allowed_routes.map((item) => String(item)) : [],
        }
      : {
          review_only: true,
          draft_only: true,
          overlay_only: true,
          execute_allowed: false,
          auto_apply: false,
          allowed_routes: [],
        },
  }
}

function mapConflict(raw: unknown, index: number): ManifestConflict {
  if (!isRecord(raw)) {
    return {
      id: `conflict-${index}`,
      row_id: '',
      type: 'unknown',
      severity: 'warning',
      source_path: '',
      target_path: '',
      reason: 'Unknown conflict',
      status: 'open',
    }
  }
  const severity = raw.severity === 'error' ? 'error' : 'warning'
  const status = raw.status === 'resolved' || raw.status === 'ignored' ? raw.status : 'open'
  return {
    id: String(raw.id ?? `conflict-${index}`),
    row_id: String(raw.row_id ?? raw.hash8 ?? ''),
    type: String(raw.type ?? raw.error_code ?? 'conflict'),
    severity,
    source_path: String(raw.source_path ?? raw.path ?? ''),
    target_path: String(raw.target_path ?? raw.new_path ?? ''),
    reason: String(raw.reason ?? raw.message ?? 'Conflict detected'),
    suggested_target: typeof raw.suggested_target === 'string' ? raw.suggested_target : undefined,
    status,
  }
}

function mapRuntimeSettings(raw: unknown): RuntimeSettings {
  if (!isRecord(raw)) {
    throw new Error('Invalid runtime settings payload')
  }
  const analyzeDefaultsRaw = isJsonRecord(raw.analyze_defaults) ? raw.analyze_defaults : {}
  return {
    workspace_root: String(raw.workspace_root ?? ''),
    runtime_env_path: String(raw.runtime_env_path ?? ''),
    input_root: String(raw.input_root ?? ''),
    output_root: String(raw.output_root ?? ''),
    allowed_root: String(raw.allowed_root ?? ''),
    manifest_root: String(raw.manifest_root ?? ''),
    artifact_root: String(raw.artifact_root ?? ''),
    has_api_key: Boolean(raw.has_api_key),
    api_key_masked: String(raw.api_key_masked ?? ''),
    api_key_source:
      raw.api_key_source === 'env' || raw.api_key_source === 'runtime_env' || raw.api_key_source === 'missing' // pragma: allowlist secret
        ? raw.api_key_source
        : 'missing',
    api_key_status:
      raw.api_key_status === 'configured' || raw.api_key_status === 'placeholder' || raw.api_key_status === 'missing' // pragma: allowlist secret
        ? raw.api_key_status
        : 'missing',
    model: String(raw.model ?? ''),
    model_source: raw.model_source === 'env' || raw.model_source === 'runtime_env' ? raw.model_source : 'default',
    active_strategy_pack_id: String(raw.active_strategy_pack_id ?? ''),
    input_root_exists: Boolean(raw.input_root_exists),
    output_root_exists: Boolean(raw.output_root_exists),
    ready: Boolean(raw.ready),
    analyze_defaults: {
      workers: Number(analyzeDefaultsRaw.workers ?? 1),
      categories: Array.isArray(analyzeDefaultsRaw.categories) ? analyzeDefaultsRaw.categories.map((item) => String(item)) : [],
      max_files: Number(analyzeDefaultsRaw.max_files ?? 0),
      max_total_mb: Number(analyzeDefaultsRaw.max_total_mb ?? 0),
      max_file_mb: Number(analyzeDefaultsRaw.max_file_mb ?? 0),
    },
    missing: Array.isArray(raw.missing) ? raw.missing.map((item) => String(item)) : [],
    warnings: Array.isArray(raw.warnings) ? raw.warnings.map((item) => String(item)) : [],
    checked_at: String(raw.checked_at ?? ''),
  }
}

function mapPreview(raw: unknown, rowId: string): PreviewPayload {
  if (!isRecord(raw)) {
    return { row_id: rowId, media_type: 'unknown' }
  }
  return {
    row_id: String(raw.row_id ?? rowId),
    media_type: String(raw.media_type ?? 'unknown'),
    thumbnail_url: typeof raw.thumbnail_url === 'string' ? raw.thumbnail_url : undefined,
    summary: typeof raw.summary === 'string' ? raw.summary : undefined,
    duration_s: typeof raw.duration_s === 'number' ? raw.duration_s : undefined,
    pages: typeof raw.pages === 'number' ? raw.pages : undefined,
    mime: typeof raw.mime === 'string' ? raw.mime : undefined,
    extra: isJsonRecord(raw.extra) ? Object.fromEntries(Object.entries(raw.extra).map(([key, value]) => [key, String(value)])) : undefined,
  }
}

function mapPreviewFromRow(row: ManifestRow): PreviewPayload {
  return {
    row_id: row.id,
    media_type: row.media_type,
    summary: row.notes || row.title,
    duration_s: row.metadata.duration_s ? Number(row.metadata.duration_s) : undefined,
    pages: row.metadata.pages ? Number(row.metadata.pages) : undefined,
    mime: row.metadata.mime,
    extra: row.metadata,
  }
}

function toManifestBackendPatch(patch: ManifestRowPatch): Record<string, unknown> {
  const aiPatch: Record<string, unknown> = {}
  if (patch.category !== undefined) {
    aiPatch.category = patch.category
  }
  if (patch.title !== undefined) {
    aiPatch.title = patch.title
  }
  if (patch.tags !== undefined) {
    aiPatch.tags = patch.tags
  }
  if (patch.notes !== undefined) {
    aiPatch.notes = patch.notes
  }

  const output: Record<string, unknown> = {}
  if (Object.keys(aiPatch).length > 0) {
    output.ai = aiPatch
  }
  if (patch.target_suggestion !== undefined) {
    output.new_path = patch.target_suggestion
  }
  if (patch.ignore !== undefined) {
    output.ignore = patch.ignore
  }
  return output
}

function mapPreferenceItems(raw: unknown): PreferenceItem[] {
  if (!isJsonRecord(raw) || !Array.isArray(raw.items)) {
    return []
  }
  return raw.items
    .filter(isJsonRecord)
    .map((item) => ({
      key: String(item.key ?? ''),
      value: isJsonRecord(item.value) ? item.value : {},
      created_at: typeof item.created_at === 'string' ? item.created_at : undefined,
      updated_at: typeof item.updated_at === 'string' ? item.updated_at : undefined,
    }))
    .filter((item) => item.key.length > 0)
}

function mapReviewRule(raw: unknown): ReviewRule {
  if (!isJsonRecord(raw)) {
    throw new Error('Invalid review rule payload')
  }
  const conditions = isJsonRecord(raw.conditions) ? raw.conditions : {}
  const actions = isJsonRecord(raw.actions) ? raw.actions : {}
  return {
    id: String(raw.id ?? ''),
    name: String(raw.name ?? ''),
    scope: raw.scope === 'report' || raw.scope === 'jobs' ? raw.scope : 'manifest',
    description: typeof raw.description === 'string' ? raw.description : '',
    version: Number(raw.version ?? 1),
    conditions: {
      query: typeof conditions.query === 'string' ? conditions.query : '',
      statuses: Array.isArray(conditions.statuses) ? conditions.statuses.map((item) => String(item)) : [],
      media_types: Array.isArray(conditions.media_types) ? conditions.media_types.map((item) => String(item)) : [],
      categories: Array.isArray(conditions.categories) ? conditions.categories.map((item) => String(item)) : [],
      review_buckets: Array.isArray(conditions.review_buckets) ? conditions.review_buckets.map((item) => String(item)) : [],
      min_confidence: typeof conditions.min_confidence === 'number' ? conditions.min_confidence : undefined,
      max_confidence: typeof conditions.max_confidence === 'number' ? conditions.max_confidence : undefined,
      has_conflict: typeof conditions.has_conflict === 'boolean' ? conditions.has_conflict : undefined,
      ignore_state: typeof conditions.ignore_state === 'boolean' ? conditions.ignore_state : undefined,
    },
    actions: {
      set_category: typeof actions.set_category === 'string' ? actions.set_category : undefined,
      set_ignore: typeof actions.set_ignore === 'boolean' ? actions.set_ignore : undefined,
      target_pattern: typeof actions.target_pattern === 'string' ? actions.target_pattern : undefined,
    },
    created_at: typeof raw.created_at === 'string' ? raw.created_at : undefined,
    updated_at: typeof raw.updated_at === 'string' ? raw.updated_at : undefined,
  }
}

function mapCollectionSummary(raw: unknown): CollectionSummary {
  if (!isJsonRecord(raw)) {
    return {
      id: '',
      title: 'Collection',
      reason: '',
      confidence: 0,
      row_ids: [],
      kind: '',
      next_step: '',
      capture_day: '',
      batch_hint: '',
      source_root: '',
      dominant_media_type: '',
      media_types: [],
      explainability: [],
    }
  }
  return {
    id: String(raw.id ?? ''),
    title: String(raw.title ?? 'Collection'),
    reason: String(raw.reason ?? ''),
    confidence: Number(raw.confidence ?? 0),
    row_ids: Array.isArray(raw.row_ids) ? raw.row_ids.map((item) => String(item)) : [],
    kind: String(raw.kind ?? ''),
    next_step: String(raw.next_step ?? ''),
    capture_day: String(raw.capture_day ?? ''),
    batch_hint: String(raw.batch_hint ?? ''),
    source_root: String(raw.source_root ?? ''),
    dominant_media_type: String(raw.dominant_media_type ?? ''),
    media_types: Array.isArray(raw.media_types) ? raw.media_types.map((item) => String(item)) : [],
    explainability: Array.isArray(raw.explainability) ? raw.explainability.map((item) => String(item)) : [],
  }
}

function mapReviewQueuePayload(raw: unknown): ReviewQueuePayload {
  if (!isJsonRecord(raw)) {
    throw new Error('Invalid review queue payload')
  }
  return {
    job: isJsonRecord(raw.job) ? mapJob(raw.job) : null,
    job_id: String(raw.job_id ?? ''),
    manifest_path: String(raw.manifest_path ?? ''),
    overlay_path: String(raw.overlay_path ?? ''),
    overlay_updated_at: typeof raw.overlay_updated_at === 'string' ? raw.overlay_updated_at : undefined,
    summary: {
      total: Number((raw.summary as Record<string, unknown> | undefined)?.total ?? 0),
      auto_safe: Number((raw.summary as Record<string, unknown> | undefined)?.auto_safe ?? 0),
      needs_review: Number((raw.summary as Record<string, unknown> | undefined)?.needs_review ?? 0),
      conflict: Number((raw.summary as Record<string, unknown> | undefined)?.conflict ?? 0),
      blocked: Number((raw.summary as Record<string, unknown> | undefined)?.blocked ?? 0),
    },
    copilot_summary: mapCopilotSummary(raw.copilot_summary),
    collections: Array.isArray(raw.collections) ? raw.collections.map(mapCollectionSummary) : [],
    rows: Array.isArray(raw.rows) ? raw.rows.map(mapManifestRow) : [],
    returned: Number(raw.returned ?? 0),
  }
}

function mapStrategyPack(raw: unknown): StrategyPack {
  if (!isJsonRecord(raw)) {
    throw new Error('Invalid strategy pack payload')
  }
  return {
    id: String(raw.id ?? ''),
    name: String(raw.name ?? ''),
    description: String(raw.description ?? ''),
    categories: Array.isArray(raw.categories) ? raw.categories.map((item) => String(item)) : [],
    model: typeof raw.model === 'string' ? raw.model : undefined,
    workers: Number(raw.workers ?? 1),
    review_confidence_threshold: Number(raw.review_confidence_threshold ?? 0.8),
    default_rule_ids: Array.isArray(raw.default_rule_ids) ? raw.default_rule_ids.map((item) => String(item)) : [],
    default_template_patterns: Array.isArray(raw.default_template_patterns)
      ? raw.default_template_patterns.map((item) => String(item))
      : [],
    defaults: isJsonRecord(raw.defaults) ? raw.defaults : {},
    explainability: isJsonRecord(raw.explainability)
      ? Object.fromEntries(Object.entries(raw.explainability).map(([key, value]) => [key, String(value)]))
      : {},
  }
}

function mapLearnedRule(raw: unknown): LearnedRule {
  if (!isJsonRecord(raw)) {
    throw new Error('Invalid learned rule payload')
  }
  return {
    id: String(raw.id ?? ''),
    signal_key: String(raw.signal_key ?? ''),
    signal_value: String(raw.signal_value ?? ''),
    suggestion_type: String(raw.suggestion_type ?? ''),
    suggestion_value: String(raw.suggestion_value ?? ''),
    confidence: Number(raw.confidence ?? 0),
    count: Number(raw.count ?? 0),
    updated_at: String(raw.updated_at ?? ''),
    confidence_label:
      raw.confidence_label === 'high' || raw.confidence_label === 'medium' || raw.confidence_label === 'weak'
        ? raw.confidence_label
        : 'weak',
    strength:
      raw.strength === 'strong' || raw.strength === 'medium' || raw.strength === 'weak'
        ? raw.strength
        : 'weak',
    reuse_scope:
      raw.reuse_scope === 'reusable' || raw.reuse_scope === 'transient'
        ? raw.reuse_scope
        : 'transient',
    source: typeof raw.source === 'string' ? raw.source : '',
    reason: typeof raw.reason === 'string' ? raw.reason : '',
    explanation: typeof raw.explanation === 'string' ? raw.explanation : '',
    scope_reason: typeof raw.scope_reason === 'string' ? raw.scope_reason : '',
  }
}

function mapRuleDraftResponse(raw: unknown): ReviewRuleDraftResponse {
  if (!isJsonRecord(raw) || !isJsonRecord(raw.draft)) {
    throw new Error('Invalid review rule draft payload')
  }
  const draft = raw.draft
  return {
    job_id: String(raw.job_id ?? ''),
    selected_count: Number(raw.selected_count ?? 0),
    selected_row_ids: Array.isArray(raw.selected_row_ids) ? raw.selected_row_ids.map((item) => String(item)) : [],
    mode: 'draft_only',
    save_allowed: false,
    apply_allowed: false,
    execute_allowed: false,
    draft: {
      id: typeof draft.id === 'string' ? draft.id : undefined,
      name: String(draft.name ?? ''),
      scope: draft.scope === 'report' || draft.scope === 'jobs' ? draft.scope : 'manifest',
      description: typeof draft.description === 'string' ? draft.description : '',
      version: Number(draft.version ?? 1),
      mode: 'draft_only',
      draft_source: typeof draft.draft_source === 'string' ? draft.draft_source : '',
      conditions: isJsonRecord(draft.conditions)
        ? {
            query: typeof draft.conditions.query === 'string' ? draft.conditions.query : '',
            statuses: Array.isArray(draft.conditions.statuses) ? draft.conditions.statuses.map((item) => String(item)) : [],
            media_types: Array.isArray(draft.conditions.media_types) ? draft.conditions.media_types.map((item) => String(item)) : [],
            categories: Array.isArray(draft.conditions.categories) ? draft.conditions.categories.map((item) => String(item)) : [],
            review_buckets: Array.isArray(draft.conditions.review_buckets)
              ? draft.conditions.review_buckets.map((item) => String(item))
              : [],
          }
        : { query: '', statuses: [], media_types: [], categories: [], review_buckets: [] },
      actions: isJsonRecord(draft.actions)
        ? {
            set_category: typeof draft.actions.set_category === 'string' ? draft.actions.set_category : undefined,
            set_ignore: typeof draft.actions.set_ignore === 'boolean' ? draft.actions.set_ignore : undefined,
            target_pattern: typeof draft.actions.target_pattern === 'string' ? draft.actions.target_pattern : undefined,
          }
        : {},
      warnings: Array.isArray(draft.warnings) ? draft.warnings.map((item) => String(item)) : [],
      example_row_ids: Array.isArray(draft.example_row_ids) ? draft.example_row_ids.map((item) => String(item)) : [],
      explainability: isJsonRecord(draft.explainability)
        ? {
            selected_count: Number(draft.explainability.selected_count ?? 0),
            selected_row_ids: Array.isArray(draft.explainability.selected_row_ids)
              ? draft.explainability.selected_row_ids.map((item) => String(item))
              : [],
            shared_media_types: Array.isArray(draft.explainability.shared_media_types)
              ? draft.explainability.shared_media_types.map((item) => String(item))
              : [],
            shared_review_buckets: Array.isArray(draft.explainability.shared_review_buckets)
              ? draft.explainability.shared_review_buckets.map((item) => String(item))
              : [],
            shared_query: typeof draft.explainability.shared_query === 'string' ? draft.explainability.shared_query : '',
            inferred_actions: Array.isArray(draft.explainability.inferred_actions)
              ? draft.explainability.inferred_actions.map((item) => String(item))
              : [],
            save_allowed: false,
            apply_allowed: false,
          }
        : {
            selected_count: 0,
            selected_row_ids: [],
            shared_media_types: [],
            shared_review_buckets: [],
            shared_query: '',
            inferred_actions: [],
            save_allowed: false,
            apply_allowed: false,
          },
    },
    warnings: Array.isArray(raw.warnings) ? raw.warnings.map((item) => String(item)) : [],
  }
}

function mapBatchTriageResponse(raw: unknown): ReviewQueuePayload & ReviewQueueBatchTriageMeta {
  const queue = mapReviewQueuePayload(raw)
  if (!isJsonRecord(raw)) {
    return {
      ...queue,
      applied_count: 0,
      mode: '',
      execute_allowed: false,
    }
  }
  return {
    ...queue,
    applied_count: Number(raw.applied_count ?? 0),
    mode: String(raw.mode ?? ''),
    execute_allowed: Boolean(raw.execute_allowed),
  }
}

function mapWatchSource(raw: unknown): WatchSource {
  if (!isJsonRecord(raw)) {
    throw new Error('Invalid watch source payload')
  }
  return {
    id: String(raw.id ?? ''),
    name: String(raw.name ?? ''),
    input_root: String(raw.input_root ?? ''),
    enabled: Boolean(raw.enabled),
    strategy_pack_id: String(raw.strategy_pack_id ?? ''),
    created_at: String(raw.created_at ?? ''),
    updated_at: String(raw.updated_at ?? ''),
    strategy_pack: isJsonRecord(raw.strategy_pack) ? mapStrategyPack(raw.strategy_pack) : undefined,
  }
}

function mapInboxBatch(raw: unknown): InboxBatch {
  if (!isJsonRecord(raw)) {
    throw new Error('Invalid inbox batch payload')
  }
  return {
    id: String(raw.id ?? ''),
    watch_source_id: String(raw.watch_source_id ?? ''),
    source_name: String(raw.source_name ?? raw.watch_source_name ?? ''),
    input_root: String(raw.input_root ?? ''),
    file_count: Number(raw.file_count ?? 0),
    file_paths: Array.isArray(raw.file_paths) ? raw.file_paths.map((item) => String(item)) : [],
    strategy_pack_id: String(raw.strategy_pack_id ?? ''),
    strategy_pack: isJsonRecord(raw.strategy_pack) ? mapStrategyPack(raw.strategy_pack) : undefined,
    analyze_ready: typeof raw.analyze_ready === 'boolean' ? raw.analyze_ready : false,
    discovery_mode: String(raw.discovery_mode ?? ''),
    analyze_defaults: isJsonRecord(raw.analyze_defaults)
      ? {
          model: String(raw.analyze_defaults.model ?? ''),
          categories: String(raw.analyze_defaults.categories ?? ''),
          workers: Number(raw.analyze_defaults.workers ?? 1),
          max_files: Number(raw.analyze_defaults.max_files ?? 0),
          max_total_mb: Number(raw.analyze_defaults.max_total_mb ?? 0),
          max_file_mb: Number(raw.analyze_defaults.max_file_mb ?? 0),
          offline: Boolean(raw.analyze_defaults.offline),
        }
      : {
          model: '',
          categories: '',
          workers: 1,
          max_files: 0,
          max_total_mb: 0,
          max_file_mb: 0,
          offline: false,
        },
    analyze_action: isJsonRecord(raw.analyze_action)
      ? {
          method: String(raw.analyze_action.method ?? ''),
          path: String(raw.analyze_action.path ?? ''),
          payload: isJsonRecord(raw.analyze_action.payload) ? raw.analyze_action.payload : {},
        }
      : { method: '', path: '', payload: {} },
    analyze_job_id: String(raw.analyze_job_id ?? ''),
  }
}

function mapInboxAnalyzeResponse(raw: unknown): InboxAnalyzeResponse {
  if (!isJsonRecord(raw) || !isJsonRecord(raw.job)) {
    throw new Error('Invalid inbox analyze response')
  }
  return {
    job: mapJob(raw.job),
    job_id: String(raw.job_id ?? ''),
    mode: String(raw.mode ?? ''),
    batch: isJsonRecord(raw.batch) ? mapInboxBatch(raw.batch) : mapInboxBatch({}),
    strategy_pack: isJsonRecord(raw.strategy_pack) ? mapStrategyPack(raw.strategy_pack) : undefined,
    review_next: isJsonRecord(raw.review_next) ? raw.review_next : {},
  }
}

function mapJobReportResponse(raw: unknown): { job_id: string; report_path: string; report: Record<string, unknown> } {
  if (!isJsonRecord(raw) || !isJsonRecord(raw.report)) {
    throw new Error('Invalid job report payload')
  }
  return {
    job_id: String(raw.job_id ?? ''),
    report_path: String(raw.report_path ?? ''),
    report: raw.report,
  }
}

function subscribeToEventStream(path: string, handlers: EventStreamHandlers): () => void {
  if (typeof window === 'undefined' || typeof EventSource === 'undefined') {
    handlers.onState?.('unsupported')
    return () => {
      handlers.onState?.('closed')
    }
  }

  handlers.onState?.('connecting')
  const source = new EventSource(`${API_ROOT}${path}`)
  const handlePayload = (rawData: string) => {
    try {
      handlers.onMessage(JSON.parse(rawData) as unknown)
    } catch {
      handlers.onMessage({ message: rawData })
    }
  }

  source.onopen = () => {
    handlers.onState?.('open')
  }

  source.onmessage = (event) => {
    handlePayload(event.data)
  }
  source.addEventListener('snapshot', (event) => handlePayload((event as MessageEvent<string>).data))
  source.addEventListener('event', (event) => handlePayload((event as MessageEvent<string>).data))
  source.addEventListener('done', (event) => handlePayload((event as MessageEvent<string>).data))

  source.onerror = () => {
    handlers.onState?.('error')
    source.close()
  }

  return () => {
    source.close()
    handlers.onState?.('closed')
  }
}

export function subscribeJobEvents(jobId: string, handlers: EventStreamHandlers): () => void {
  return subscribeToEventStream(contractPath(apiContract.streamJob(jobId)), handlers)
}

export function subscribeJobs(handlers: EventStreamHandlers): () => void {
  if (typeof window === 'undefined') {
    handlers.onState?.('unsupported')
    return () => {
      handlers.onState?.('closed')
    }
  }

  let pollingTimer: number | null = null
  const startPolling = (state: StreamState) => {
    handlers.onState?.(state)
    if (pollingTimer !== null) {
      return
    }
    pollingTimer = window.setInterval(() => {
      handlers.onMessage({ type: 'poll' })
    }, JOBS_POLL_INTERVAL_MS)
  }

  if (typeof EventSource === 'undefined') {
    startPolling('unsupported')
    return () => {
      if (pollingTimer !== null) {
        window.clearInterval(pollingTimer)
      }
      handlers.onState?.('closed')
    }
  }

  handlers.onState?.('connecting')
  const source = new EventSource(apiContract.streamJobs)
  source.onopen = () => {
    handlers.onState?.('open')
  }
  source.onmessage = (event) => {
    try {
      handlers.onMessage(JSON.parse(event.data) as unknown)
    } catch {
      handlers.onMessage({ message: event.data })
    }
  }
  source.onerror = () => {
    source.close()
    startPolling('unsupported')
  }

  return () => {
    source.close()
    if (pollingTimer !== null) {
      window.clearInterval(pollingTimer)
    }
    handlers.onState?.('closed')
  }
}

export async function listJobs(query?: JobsQuery): Promise<Job[]> {
  const payload = await requestJson<unknown[]>(`${contractPath(apiContract.listJobs)}${buildQuery(query)}`)
  return payload.map(mapJob)
}

export async function getJob(jobId: string): Promise<Job | undefined> {
  const payload = await requestJson<unknown>(contractPath(apiContract.getJob(jobId)))
  return mapJob(payload)
}

export async function getJobEvents(jobId: string): Promise<JobEvent[]> {
  const payload = await requestJson<{ events?: unknown[] }>(contractPath(apiContract.getJobEvents(jobId)))
  return Array.isArray(payload.events) ? payload.events.map(mapEvent) : []
}

export async function getManifestRows(jobId: string): Promise<ManifestRow[]> {
  let payload: { rows?: unknown[] }
  try {
    payload = await requestJson<{ rows?: unknown[] }>(contractPath(apiContract.getManifestView(jobId)))
  } catch (error) {
    if (!(error instanceof ApiRequestError) || error.status !== 404) {
      throw error
    }
    payload = await requestJson<{ rows?: unknown[] }>(contractPath(apiContract.getManifest(jobId)))
  }
  return Array.isArray(payload.rows) ? payload.rows.map(mapManifestRow) : []
}

export async function getReviewQueue(jobId: string): Promise<ReviewQueuePayload> {
  const payload = await requestJson<unknown>(contractPath(apiContract.getReviewQueue(jobId)))
  return mapReviewQueuePayload(payload)
}

export async function patchManifestRows(jobId: string, patches: ManifestRowPatch[]): Promise<ManifestRow[]> {
  const operations = patches
    .map((patch) => {
      const backendPatch = toManifestBackendPatch(patch)
      if (Object.keys(backendPatch).length === 0) {
        return null
      }
      return {
        row_id: patch.row_id,
        patch: backendPatch,
      }
    })
    .filter((item): item is { row_id: string; patch: Record<string, unknown> } => item !== null)

  if (operations.length === 0) {
    return getManifestRows(jobId)
  }

  const payload = await requestJson<{ rows?: unknown[] }>(contractPath(apiContract.patchManifestBatch(jobId)), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operations }),
  })
  if (!Array.isArray(payload.rows)) {
    throw new Error('Batch save failed: the backend did not return updated manifest rows.')
  }
  return payload.rows.map(mapManifestRow)
}

export async function getManifestConflicts(jobId: string): Promise<ManifestConflict[]> {
  const payload = await requestJson<{ conflicts?: unknown[] }>(contractPath(apiContract.getManifestConflicts(jobId)))
  return Array.isArray(payload.conflicts) ? payload.conflicts.map(mapConflict) : []
}

export async function resolveManifestConflict(
  jobId: string,
  conflictId: string,
  action: 'accept_suggestion' | 'ignore' | 'manual_target',
  targetPath?: string,
): Promise<boolean> {
  const conflicts = await getManifestConflicts(jobId)
  const targetConflict = conflicts.find((item) => item.id === conflictId)
  const rowId = targetConflict?.row_id ?? conflictId

  if (action === 'ignore') {
    try {
      await patchManifestRows(jobId, [{ row_id: rowId, ignore: true, target_suggestion: '' }])
      return true
    } catch {
      return false
    }
  }

  const nextPath =
    action === 'manual_target'
      ? targetPath?.trim() ?? ''
      : (targetConflict?.suggested_target ?? targetConflict?.target_path ?? '').trim()

  if (!nextPath) {
    return false
  }

  try {
    await requestJson<unknown>(contractPath(apiContract.resolveManifestConflicts(jobId)), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resolutions: [{ row_id: rowId, new_path: nextPath }],
      }),
    })
    return true
  } catch {
    return false
  }
}

export async function getManifestPreview(jobId: string, rowId: string, options?: PreviewRequestOptions): Promise<PreviewPayload | undefined> {
  try {
    const payload = await requestJson<unknown>(contractPath(apiContract.getManifestPreview(jobId, rowId)), {
      signal: options?.signal,
    })
    return mapPreview(payload, rowId)
  } catch (error) {
    try {
      const rows = await getManifestRows(jobId)
      const row = rows.find((item) => item.id === rowId)
      if (row) {
        return mapPreviewFromRow(row)
      }
    } catch {
      // keep original error path below
    }
    if (options?.throwOnError) {
      throw error
    }
    return undefined
  }
}

export async function getReport(jobId: string): Promise<JobSummary> {
  const payload = await requestJson<{ report?: unknown }>(contractPath(apiContract.getReport(jobId)))
  return (
    mapSummary(payload.report) ?? {
      total: 0,
      with_error: 0,
      by_media_type: {},
      by_category: {},
      by_status: {},
      error_codes: {},
    }
  )
}

export async function getJobReport(jobId: string): Promise<{ job_id: string; report_path: string; report: Record<string, unknown> }> {
  const payload = await requestJson<unknown>(contractPath(apiContract.getReport(jobId)))
  return mapJobReportResponse(payload)
}

export async function createAnalyzeJob(options: AnalyzeOptions): Promise<Job> {
  if (options.inputMode === 'upload') {
    const body = new FormData()
    body.append('input_mode', 'upload')
    body.append('offline', String(Boolean(options.offline)))
    if (options.model) {
      body.append('model', options.model)
    }
    if (options.categories) {
      body.append('categories', options.categories)
    }
    if (typeof options.workers === 'number' && Number.isFinite(options.workers)) {
      body.append('workers', String(options.workers))
    }
    if (typeof options.maxFiles === 'number' && Number.isFinite(options.maxFiles)) {
      body.append('max_files', String(options.maxFiles))
    }
    if (typeof options.maxTotalMb === 'number' && Number.isFinite(options.maxTotalMb)) {
      body.append('max_total_mb', String(options.maxTotalMb))
    }
    if (typeof options.maxFileMb === 'number' && Number.isFinite(options.maxFileMb)) {
      body.append('max_file_mb', String(options.maxFileMb))
    }
    for (const file of options.files ?? []) {
      body.append('files', file)
      const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name
      body.append('relative_paths', relativePath)
    }
    const payload = await requestJson<unknown>(contractPath(apiContract.createAnalyzeJob), { method: 'POST', body })
    return mapJob(payload)
  }

  const payload = await requestJson<unknown>(contractPath(apiContract.createAnalyzeJob), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      input_mode: 'directory',
      input_directory: options.inputDirectory,
      model: options.model,
      categories: options.categories,
      workers: options.workers,
      max_files: options.maxFiles,
      max_total_mb: options.maxTotalMb,
      max_file_mb: options.maxFileMb,
      offline: Boolean(options.offline),
    }),
  })
  return mapJob(payload)
}

export async function getRuntimeSettings(): Promise<RuntimeSettings> {
  const payload = await requestJson<unknown>(contractPath(apiContract.getRuntimeSettings))
  return mapRuntimeSettings(payload)
}

export async function updateRuntimeSettings(input: RuntimeSettingsUpdateInput): Promise<RuntimeSettings> {
  const payload = await requestJson<unknown>(contractPath(apiContract.upsertRuntimeSettings), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: input.apiKey,
      clear_api_key: Boolean(input.clearApiKey),
      model: input.model,
      active_strategy_pack_id: input.activeStrategyPackId,
      input_root: input.inputRoot,
      output_root: input.outputRoot,
      workers: input.workers,
      categories: input.categories,
      max_files: input.maxFiles,
      max_total_mb: input.maxTotalMb,
      max_file_mb: input.maxFileMb,
      create_missing_dirs: input.createMissingDirs ?? true,
    }),
  })
  return mapRuntimeSettings(payload)
}

export async function validateRuntimeSettings(): Promise<RuntimeSettings> {
  const payload = await requestJson<unknown>(contractPath(apiContract.validateRuntimeSettings), {
    method: 'POST',
  })
  return mapRuntimeSettings(payload)
}

export async function createApplyJob(options: ApplyOptions): Promise<Job> {
  const payload = await requestJson<unknown>(contractPath(apiContract.createApplyJob), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      analyze_job_id: options.analyzeJobId,
      manifest_path: options.manifestPath,
      output_root: options.outputRoot,
      execute: Boolean(options.execute),
    }),
  })
  return mapJob(payload)
}

export async function createRollbackJob(options: RollbackOptions): Promise<Job> {
  const payload = await requestJson<unknown>(contractPath(apiContract.createRollbackJob), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      analyze_job_id: options.analyzeJobId,
      manifest_path: options.manifestPath,
      execute: Boolean(options.execute),
      source_job_id: options.sourceJobId,
      allowed_root: options.allowedRoot,
      strict_integrity: Boolean(options.strictIntegrity),
      audit_reason: options.auditReason,
    }),
  })
  return mapJob(payload)
}

export async function cancelJob(jobId: string): Promise<Job> {
  const payload = await requestJson<unknown>(contractPath(apiContract.cancelJob(jobId)), {
    method: 'POST',
  })
  return mapJob(payload)
}

export async function retryJob(jobId: string): Promise<Job> {
  const payload = await requestJson<unknown>(contractPath(apiContract.retryJob(jobId)), {
    method: 'POST',
  })
  return mapJob(payload)
}

export async function listSavedViews(scope: SavedView['scope']): Promise<SavedView[]> {
  const payload = await requestJson<unknown>(contractPath(apiContract.listSavedViews))
  const items = mapPreferenceItems(payload)
  return items
    .filter((item) => {
      const itemScope = typeof item.value.scope === 'string' ? item.value.scope : 'manifest'
      return itemScope === scope
    })
    .map((item) => ({
      id: item.key,
      name: typeof item.value.name === 'string' ? item.value.name : item.key,
      scope,
      query: isJsonRecord(item.value.query) ? Object.fromEntries(Object.entries(item.value.query).map(([k, v]) => [k, String(v)])) : {},
      created_at: item.created_at ?? new Date().toISOString(),
    }))
}

export async function createSavedView(input: Omit<SavedView, 'id' | 'created_at'>): Promise<SavedView> {
  const nextId = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `view-${Date.now()}`
  const payload = {
    key: nextId,
    value: {
      name: input.name,
      scope: input.scope,
      query: input.query,
    },
  }

  const response = await requestJson<unknown>(contractPath(apiContract.upsertSavedView), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!isJsonRecord(response)) {
    throw new Error('Saving the view failed: the backend returned an unrecognized response.')
  }
  return {
    id: String(response.key ?? nextId),
    name: input.name,
    scope: input.scope,
    query: input.query,
    created_at: String(response.created_at ?? response.updated_at ?? new Date().toISOString()),
  }
}

export async function deleteSavedView(id: string): Promise<void> {
  await requestJson<unknown>(`${contractPath(apiContract.deleteSavedView)}${buildQuery({ key: id })}`, { method: 'DELETE' })
}

export async function listNamingTemplates(): Promise<NamingTemplate[]> {
  const payload = await requestJson<unknown>(contractPath(apiContract.listNamingTemplates))
  const items = mapPreferenceItems(payload)
  return items.map((item, index) => ({
    id: item.key || `template-${index}`,
    name: typeof item.value.name === 'string' ? item.value.name : `Template ${index + 1}`,
    pattern: typeof item.value.pattern === 'string' ? item.value.pattern : '{category}/{title}__{hash8}',
    description: typeof item.value.description === 'string' ? item.value.description : undefined,
    created_at: item.created_at ?? new Date().toISOString(),
  }))
}

export async function createNamingTemplate(input: Omit<NamingTemplate, 'id' | 'created_at'>): Promise<NamingTemplate> {
  const nextId = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `tpl-${Date.now()}`
  const payload = await requestJson<unknown>(contractPath(apiContract.upsertNamingTemplate), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      key: nextId,
      value: {
        name: input.name,
        pattern: input.pattern,
        description: input.description,
      },
    }),
  })
  if (!isJsonRecord(payload)) {
    throw new Error('Creating the naming template failed: the backend returned an unrecognized response.')
  }
  return {
    id: String(payload.key ?? nextId),
    name: input.name,
    pattern: input.pattern,
    description: input.description,
    created_at: String(payload.created_at ?? payload.updated_at ?? new Date().toISOString()),
  }
}

export async function deleteNamingTemplate(id: string): Promise<void> {
  await requestJson<unknown>(`${contractPath(apiContract.deleteNamingTemplate)}${buildQuery({ key: id })}`, { method: 'DELETE' })
}

export async function listReviewRules(): Promise<ReviewRule[]> {
  const payload = await requestJson<unknown>(contractPath(apiContract.listReviewRules))
  if (!isJsonRecord(payload) || !Array.isArray(payload.items)) {
    return []
  }
  return payload.items.map(mapReviewRule)
}

export async function createReviewRule(input: Omit<ReviewRule, 'id'> & { id?: string }): Promise<ReviewRule> {
  const payload = await requestJson<unknown>(contractPath(apiContract.upsertReviewRule), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  return mapReviewRule(payload)
}

export async function deleteReviewRule(id: string): Promise<void> {
  await requestJson<unknown>(`${contractPath(apiContract.deleteReviewRule)}${buildQuery({ key: id })}`, { method: 'DELETE' })
}

export async function previewReviewRule(jobId: string, ruleId?: string, rule?: Omit<ReviewRule, 'id'> & { id?: string }): Promise<RulePreview> {
  const payload = await requestJson<unknown>(contractPath(apiContract.previewReviewRule(jobId)), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rule_id: ruleId, rule }),
  })
  if (!isJsonRecord(payload)) {
    throw new Error('Invalid review rule preview payload')
  }
  return {
    matched_row_ids: Array.isArray(payload.matched_row_ids) ? payload.matched_row_ids.map((item) => String(item)) : [],
    matched_count: Number(payload.matched_count ?? 0),
    patch_preview: isJsonRecord(payload.patch_preview)
      ? Object.fromEntries(Object.entries(payload.patch_preview).map(([key, value]) => [key, isJsonRecord(value) ? value : {}]))
      : {},
  }
}

export async function applyReviewRule(jobId: string, ruleId?: string, rule?: Omit<ReviewRule, 'id'> & { id?: string }): Promise<ReviewQueuePayload> {
  const payload = await requestJson<unknown>(contractPath(apiContract.applyReviewRule(jobId)), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rule_id: ruleId, rule }),
  })
  return mapReviewQueuePayload(payload)
}

export async function draftReviewRuleFromExamples(jobId: string, rowIds: string[], name?: string): Promise<ReviewRuleDraftResponse> {
  const payload = await requestJson<unknown>(contractPath(apiContract.draftReviewRuleFromExamples(jobId)), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      row_ids: rowIds,
      name,
    }),
  })
  return mapRuleDraftResponse(payload)
}

export async function applyReviewQueueBatchTriage(
  jobId: string,
  payload: {
    rowIds: string[]
    setCategory?: string
    setIgnore?: boolean
  },
): Promise<ReviewQueuePayload & ReviewQueueBatchTriageMeta> {
  const raw = await requestJson<unknown>(contractPath(apiContract.batchTriageReviewQueue(jobId)), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      row_ids: payload.rowIds,
      set_category: payload.setCategory,
      set_ignore: payload.setIgnore,
    }),
  })
  return mapBatchTriageResponse(raw)
}

export async function listStrategyPacks(): Promise<{ items: StrategyPack[]; active_strategy_pack_id: string }> {
  const payload = await requestJson<unknown>(contractPath(apiContract.listStrategyPacks))
  if (!isJsonRecord(payload) || !Array.isArray(payload.items)) {
    return { items: [], active_strategy_pack_id: '' }
  }
  return {
    items: payload.items.map(mapStrategyPack),
    active_strategy_pack_id: typeof payload.active_strategy_pack_id === 'string' ? payload.active_strategy_pack_id : '',
  }
}

export async function listLearnedRules(): Promise<LearnedRule[]> {
  const payload = await requestJson<unknown>(contractPath(apiContract.listLearnedRules))
  if (!isJsonRecord(payload) || !Array.isArray(payload.items)) {
    return []
  }
  return payload.items.map(mapLearnedRule)
}

export async function resetLearnedRules(): Promise<void> {
  await requestJson<unknown>(contractPath(apiContract.resetLearnedRules), { method: 'DELETE' })
}

export async function listWatchSources(): Promise<WatchSource[]> {
  const payload = await requestJson<unknown>(contractPath(apiContract.listWatchSources))
  if (!isJsonRecord(payload) || !Array.isArray(payload.items)) {
    return []
  }
  return payload.items.map(mapWatchSource)
}

export async function upsertWatchSource(input: {
  id?: string
  name: string
  input_root: string
  enabled: boolean
  strategy_pack_id?: string
}): Promise<WatchSource> {
  const payload = await requestJson<unknown>(contractPath(apiContract.upsertWatchSource), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  return mapWatchSource(payload)
}

export async function deleteWatchSource(id: string): Promise<void> {
  await requestJson<unknown>(`${contractPath(apiContract.deleteWatchSource)}${buildQuery({ key: id })}`, { method: 'DELETE' })
}

export async function scanInbox(): Promise<InboxBatch[]> {
  const payload = await requestJson<unknown>(contractPath(apiContract.scanInbox), { method: 'POST' })
  if (!isJsonRecord(payload) || !Array.isArray(payload.items)) {
    return []
  }
  return payload.items.map(mapInboxBatch)
}

export async function startInboxAnalyze(input: {
  watchSourceId: string
  inputRoot?: string
  strategyPackId?: string
  offline?: boolean
}): Promise<InboxAnalyzeResponse> {
  const payload = await requestJson<unknown>(contractPath(apiContract.startInboxAnalyze), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      watch_source_id: input.watchSourceId,
      input_root: input.inputRoot,
      strategy_pack_id: input.strategyPackId,
      offline: Boolean(input.offline),
    }),
  })
  return mapInboxAnalyzeResponse(payload)
}
