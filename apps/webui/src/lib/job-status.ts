import type { JobStatus } from '@/lib/types'

const KNOWN_JOB_STATUSES: ReadonlySet<JobStatus> = new Set([
  'queued',
  'running',
  'cancelling',
  'succeeded',
  'failed',
  'cancelled',
])

export function normalizeJobStatus(value: unknown): JobStatus {
  if (typeof value === 'string' && KNOWN_JOB_STATUSES.has(value as JobStatus)) {
    return value as JobStatus
  }
  return 'queued'
}
