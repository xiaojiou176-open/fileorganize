import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { RuleStudioSheet } from '@/components/review/rule-studio-sheet'

const mocks = vi.hoisted(() => ({
  listReviewRules: vi.fn(async () => [{ id: 'rule-1', name: 'Trip rule', scope: 'manifest', description: 'saved', version: 1, conditions: {}, actions: {}, created_at: 'now' }]),
  previewReviewRule: vi.fn(async () => ({ matched_row_ids: ['0'], matched_count: 1, patch_preview: { '0': { category: '旅行' } } })),
  createReviewRule: vi.fn(async () => ({ id: 'rule-1', name: 'Trip rule', scope: 'manifest', description: '', version: 1, conditions: {}, actions: {}, created_at: 'now' })),
  applyReviewRule: vi.fn(async () => ({
    job: null,
    job_id: 'job-1',
    manifest_path: '/tmp/manifest.jsonl',
    overlay_path: '/tmp/overlay.json',
    summary: { total: 1, auto_safe: 0, needs_review: 1, conflict: 0, blocked: 0 },
    collections: [],
    rows: [],
    returned: 0,
  })),
  deleteReviewRule: vi.fn(async () => undefined),
}))

vi.mock('@/lib/api', () => ({
  listReviewRules: mocks.listReviewRules,
  previewReviewRule: mocks.previewReviewRule,
  createReviewRule: mocks.createReviewRule,
  applyReviewRule: mocks.applyReviewRule,
  deleteReviewRule: mocks.deleteReviewRule,
}))

describe('RuleStudioSheet', () => {
  it('previews and applies a rule', async () => {
    const onApplied = vi.fn()
    render(<RuleStudioSheet jobId="job-1" onApplied={onApplied} />)

    fireEvent.click(screen.getByRole('button', { name: 'Preview Rule' }))
    expect(await screen.findByText('Matched rows: 1')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Apply to Overlay' }))
    await waitFor(() => {
      expect(onApplied).toHaveBeenCalledTimes(1)
    })
  })

  it('loads and applies a saved rule', async () => {
    const onApplied = vi.fn()
    render(<RuleStudioSheet jobId="job-1" onApplied={onApplied} />)

    expect(await screen.findByText('Trip rule')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Load into Editor' }))
    expect(screen.getByDisplayValue('Trip rule')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Apply Saved Rule' }))
    await waitFor(() => {
      expect(mocks.applyReviewRule).toHaveBeenCalledWith('job-1', 'rule-1')
    })
  })

  it('shows a transparent notice for seeded drafts', async () => {
    const onApplied = vi.fn()
    render(
      <RuleStudioSheet
        jobId="job-1"
        onApplied={onApplied}
        seedMeta={{
          source: 'example-draft',
          title: 'Example draft loaded',
          description: 'This draft came from the backend review examples route. It is draft-only and was not saved or applied for you.',
          warnings: ['Saving is still a manual choice in Rule Studio.'],
        }}
        seedRule={{
          name: 'Draft from examples',
          scope: 'manifest',
          description: 'Generated from examples',
          version: 1,
          conditions: { query: 'trip', statuses: [], media_types: ['image'], categories: [], review_buckets: [] },
          actions: { set_category: '旅行' },
        }}
        seedRuleToken={1}
      />,
    )

    expect(await screen.findByText('Example draft loaded')).toBeInTheDocument()
    expect(screen.getByText('This draft came from the backend review examples route. It is draft-only and was not saved or applied for you.')).toBeInTheDocument()
    expect(screen.getByText('Saving is still a manual choice in Rule Studio.')).toBeInTheDocument()
  })
})
