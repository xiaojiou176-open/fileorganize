import fc from 'fast-check'
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

  it('only preserves the documented status set', () => {
    const known = new Set(['queued', 'running', 'cancelling', 'succeeded', 'failed', 'cancelled'])

    fc.assert(
      fc.property(fc.string(), (candidate) => {
        const normalized = normalizeJobStatus(candidate)
        if (known.has(candidate)) {
          expect(normalized).toBe(candidate)
        } else {
          expect(normalized).toBe('queued')
        }
      }),
    )
  })
})
