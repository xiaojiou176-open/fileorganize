import { describe, expect, it } from 'vitest'

import { normalizeJobStatus } from '@/lib/job-status'

describe('normalizeJobStatus', () => {
  it('keeps cancelling without fallback', () => {
    expect(normalizeJobStatus('cancelling')).toBe('cancelling')
  })

  it('falls back unknown values to queued', () => {
    expect(normalizeJobStatus('unknown-status')).toBe('queued')
    expect(normalizeJobStatus(undefined)).toBe('queued')
  })
})
