import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { LearnedRulesPanel } from '@/components/review/learned-rules-panel'

const mocks = vi.hoisted(() => ({
  listLearnedRules: vi.fn(async () => [
    {
      id: 'learned-1',
      signal_key: 'media_type',
      signal_value: 'image',
      suggestion_type: 'category',
      suggestion_value: '旅行',
      confidence: 0.8,
      count: 3,
      confidence_label: 'high',
      strength: 'strong',
      reuse_scope: 'reusable',
      source: 'workspace_review_learning_v1',
      reason: 'Observed 3 accepted review edit(s) mapping media_type=image to 旅行.',
      explanation: 'Observed 3 accepted review edit(s) mapping media_type=image to 旅行.',
      scope_reason: 'Reusable because the same correction was accepted multiple times.',
      updated_at: '2026-03-29T10:00:00Z',
    },
  ]),
  resetLearnedRules: vi.fn(async () => undefined),
}))

vi.mock('@/lib/api', () => ({
  listLearnedRules: mocks.listLearnedRules,
  resetLearnedRules: mocks.resetLearnedRules,
}))

describe('LearnedRulesPanel', () => {
  it('renders learned rules and allows reset', async () => {
    render(<LearnedRulesPanel />)
    expect(await screen.findByText('category: 旅行')).toBeInTheDocument()
    expect(screen.getByText('source=workspace_review_learning_v1')).toBeInTheDocument()
    expect(screen.getByText('reuse_scope=reusable')).toBeInTheDocument()
    expect(screen.getAllByText(/Observed 3 accepted review edit\(s\) mapping media_type=image to 旅行\./).length).toBeGreaterThan(0)
    expect(screen.getByText(/confidence=80% \(high\)/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Reset Learned Rules' }))
    await waitFor(() => {
      expect(mocks.resetLearnedRules).toHaveBeenCalledTimes(1)
    })
  })

  it('promotes a learned rule into the rule studio workflow', async () => {
    const onPromote = vi.fn()
    render(<LearnedRulesPanel onPromote={onPromote} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Promote to Draft' }))
    expect(onPromote).toHaveBeenCalledTimes(1)
    expect(onPromote.mock.calls[0]?.[0]).toMatchObject({ id: 'learned-1', suggestion_value: '旅行' })
  })

  it('accepts and dismisses a learned rule action', async () => {
    const onAccept = vi.fn(async () => undefined)
    render(<LearnedRulesPanel onAccept={onAccept} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Accept into Overlay' }))
    await waitFor(() => {
      expect(onAccept).toHaveBeenCalledTimes(1)
    })

    fireEvent.click(screen.getByRole('button', { name: 'Ignore for Now' }))
    await waitFor(() => {
      expect(screen.queryByText('category: 旅行')).not.toBeInTheDocument()
    })
  })
})
