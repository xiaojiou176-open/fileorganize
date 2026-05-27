import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { LogPanel } from '@/components/observability/log-panel'
import type { JobEvent } from '@/lib/types'

const toastMock = vi.hoisted(() => ({
  message: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: toastMock,
}))

describe('LogPanel', () => {
  const writeTextMock = vi.fn(async () => undefined)

  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(window.navigator, 'clipboard', {
      configurable: true,
      value: { writeText: writeTextMock },
    })
  })

  it('shows English-first controls and copies logs', async () => {
    const events: JobEvent[] = [
      {
        timestamp: '2026-03-19T12:00:00.000Z',
        level: 'info',
        message: 'Manifest loaded',
        fields: { job_id: 'job-1' },
      },
    ]

    render(
      <LogPanel
        connectionState="open"
        events={events}
        onRefresh={() => undefined}
      />,
    )

    expect(screen.getByText('SSE connected')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copy Logs' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Refresh' })).toBeInTheDocument()
    expect(screen.getByText('All levels')).toBeInTheDocument()
    expect(screen.getByText('Auto-scroll')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Copy Logs' }))

    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledTimes(1)
    })
    expect(toastMock.success).toHaveBeenCalledWith('Logs copied to clipboard.')
  })
})
