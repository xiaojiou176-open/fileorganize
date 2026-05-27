import { describe, expect, it } from 'vitest'

import { createRuleDraftFromLearnedSuggestion, explainLearnedSuggestion } from '@/components/review/review-intelligence'

describe('review intelligence helpers', () => {
  it('creates a learned-suggestion draft and explanation text', () => {
    const suggestion = {
      id: 'learned-1',
      signal_key: 'media_type',
      signal_value: 'image',
      suggestion_type: 'category',
      suggestion_value: '旅行',
      confidence: 0.8,
      count: 3,
      confidence_label: 'high' as const,
      strength: 'strong' as const,
      reuse_scope: 'reusable' as const,
      source: 'workspace_review_learning_v1',
      reason: 'Observed 3 accepted review edit(s) mapping media_type=image to 旅行.',
      explanation: 'Observed 3 accepted review edit(s) mapping media_type=image to 旅行.',
      scope_reason: 'Reusable because the same correction was accepted multiple times.',
      updated_at: '2026-03-29T10:00:00Z',
    }

    const draft = createRuleDraftFromLearnedSuggestion(suggestion, { reviewBucket: 'needs_review' })

    expect(draft.conditions.media_types).toEqual(['image'])
    expect(draft.conditions.review_buckets).toEqual(['needs_review'])
    expect(draft.actions.set_category).toBe('旅行')
    expect(draft.description).toContain('review-only')
    expect(explainLearnedSuggestion(suggestion)).toContain('Observed 3 accepted review edit(s)')
    expect(explainLearnedSuggestion(suggestion)).toContain('Confidence label: high')
    expect(explainLearnedSuggestion(suggestion)).toContain('Source: workspace_review_learning_v1.')
  })
})
