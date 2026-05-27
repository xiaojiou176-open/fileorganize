import { useCallback, useEffect, useRef, useState } from 'react'

import { getJob, getJobEvents, subscribeJobEvents } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { normalizeJobStatus } from '@/lib/job-status'
import type { Job, JobEvent } from '@/lib/types'

type LiveState = 'connecting' | 'open' | 'error' | 'unsupported' | 'closed'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function mapLiveEvent(raw: unknown): JobEvent | null {
  if (!isRecord(raw)) {
    return null
  }
  const timestamp = typeof raw.timestamp === 'string' ? raw.timestamp : null
  const level = typeof raw.level === 'string' ? raw.level : null
  const message = typeof raw.message === 'string' ? raw.message : null
  if (!timestamp || !level || !message) {
    return null
  }
  return {
    timestamp,
    level,
    message,
    fields: isRecord(raw.fields) ? raw.fields : undefined,
  }
}

function mapLiveSummary(raw: unknown): Job['summary'] {
  if (!isRecord(raw)) {
    return undefined
  }
  return {
    total: Number(raw.total ?? 0),
    with_error: Number(raw.with_error ?? 0),
    by_media_type: isRecord(raw.by_media_type) ? (raw.by_media_type as Record<string, number>) : {},
    by_category: isRecord(raw.by_category) ? (raw.by_category as Record<string, number>) : {},
    by_status: isRecord(raw.by_status) ? (raw.by_status as Record<string, number>) : {},
    error_codes: isRecord(raw.error_codes) ? (raw.error_codes as Record<string, number>) : {},
    manifest_path: typeof raw.manifest_path === 'string' ? raw.manifest_path : undefined,
    report_path: typeof raw.report_path === 'string' ? raw.report_path : undefined,
    rollback_manifest_path: typeof raw.rollback_manifest_path === 'string' ? raw.rollback_manifest_path : undefined,
    input_mode: raw.input_mode === 'directory' || raw.input_mode === 'upload' ? raw.input_mode : undefined,
    input_root: typeof raw.input_root === 'string' ? raw.input_root : undefined,
    output_root: typeof raw.output_root === 'string' ? raw.output_root : undefined,
    dry_run: typeof raw.dry_run === 'boolean' ? raw.dry_run : undefined,
    allowed_root: typeof raw.allowed_root === 'string' ? raw.allowed_root : undefined,
  }
}

function mapLiveJob(raw: unknown): Job | null {
  if (!isRecord(raw)) {
    return null
  }
  const id = typeof raw.id === 'string' || typeof raw.id === 'number' ? String(raw.id) : ''
  if (id.length === 0) {
    return null
  }

  const kind: Job['kind'] = raw.kind === 'apply' || raw.kind === 'rollback' || raw.kind === 'analyze' ? raw.kind : 'analyze'
  const status: Job['status'] = normalizeJobStatus(raw.status)
  const summary = mapLiveSummary(raw.summary)
  const manifestPath = typeof raw.manifest_path === 'string' ? raw.manifest_path : summary?.manifest_path
  const reportPath = typeof raw.report_path === 'string' ? raw.report_path : summary?.report_path
  const rollbackManifestPath =
    typeof raw.rollback_manifest_path === 'string' ? raw.rollback_manifest_path : summary?.rollback_manifest_path

  return {
    id,
    kind,
    status,
    phase: typeof raw.phase === 'string' ? raw.phase : 'queued',
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

export function useLiveJob(jobId: string, enabled = true) {
  const { t } = useI18n()
  const [jobEntry, setJobEntry] = useState<{ jobId: string; value: Job | null }>({ jobId: '', value: null })
  const [eventsEntry, setEventsEntry] = useState<{ jobId: string; value: JobEvent[] }>({ jobId: '', value: [] })
  const [stateEntry, setStateEntry] = useState<{ jobId: string; value: LiveState }>({ jobId: '', value: 'connecting' })
  const [errorEntry, setErrorEntry] = useState<{ jobId: string; value: string }>({ jobId: '', value: '' })
  const refreshTimerRef = useRef<number | null>(null)

  const refresh = useCallback(async () => {
    if (!enabled || jobId.length === 0) {
      return
    }
    try {
      const [nextJob, nextEvents] = await Promise.all([getJob(jobId), getJobEvents(jobId)])
      setJobEntry({ jobId, value: nextJob ?? null })
      setEventsEntry({ jobId, value: nextEvents })
      setErrorEntry({ jobId, value: '' })
    } catch (refreshError) {
      setErrorEntry({ jobId, value: refreshError instanceof Error ? refreshError.message : t('liveJob.refreshFailed') })
    }
  }, [enabled, jobId, t])

  const scheduleRefresh = useCallback(() => {
    if (refreshTimerRef.current !== null) {
      return
    }
    refreshTimerRef.current = window.setTimeout(() => {
      refreshTimerRef.current = null
      void refresh()
    }, 240)
  }, [refresh])

  useEffect(() => {
    if (!enabled || jobId.length === 0) {
      return
    }
    const timer = window.setTimeout(() => {
      void refresh()
    }, 0)
    return () => {
      window.clearTimeout(timer)
    }
  }, [enabled, jobId, refresh])

  useEffect(() => {
    if (!enabled || jobId.length === 0) {
      return
    }

    const unsubscribe = subscribeJobEvents(jobId, {
      onState: (nextState) => {
        setStateEntry({ jobId, value: nextState })
      },
      onMessage: (payload) => {
        if (isRecord(payload) && isRecord(payload.job)) {
          const mapped = mapLiveJob(payload.job)
          if (mapped) {
            setJobEntry({ jobId, value: mapped })
          } else {
            scheduleRefresh()
          }
          return
        }

        if (isRecord(payload) && Array.isArray(payload.events)) {
          const mapped = payload.events.map((item) => mapLiveEvent(item)).filter((item): item is JobEvent => item !== null)
          if (mapped.length > 0) {
            setEventsEntry({ jobId, value: mapped })
            return
          }
        }

        const single = mapLiveEvent(payload)
        if (single) {
          setEventsEntry((prev) => ({
            jobId,
            value: prev.jobId === jobId ? [...prev.value, single] : [single],
          }))
          return
        }

        scheduleRefresh()
      },
    })

    return () => {
      if (refreshTimerRef.current !== null) {
        window.clearTimeout(refreshTimerRef.current)
        refreshTimerRef.current = null
      }
      unsubscribe()
    }
  }, [enabled, jobId, scheduleRefresh])

  return {
    job: jobEntry.jobId === jobId ? jobEntry.value : null,
    events: eventsEntry.jobId === jobId ? eventsEntry.value : [],
    state: !enabled || jobId.length === 0 ? 'unsupported' : stateEntry.jobId === jobId ? stateEntry.value : 'connecting',
    error: errorEntry.jobId === jobId ? errorEntry.value : '',
    refresh,
  }
}
