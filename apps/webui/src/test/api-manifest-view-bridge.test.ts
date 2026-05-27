import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getManifestRows } from '@/lib/api'

function makeJsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('manifest view bridge', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('falls back to the legacy manifest endpoint only when manifest/view returns 404', async () => {
    fetchMock
      .mockResolvedValueOnce(makeJsonResponse({ detail: 'missing' }, 404))
      .mockResolvedValueOnce(
        makeJsonResponse({
          rows: [{ path: '/tmp/demo.png', media_type: 'image', ai: { title: 'demo', category: '其他', tags: [] } }],
        }),
      )

    const rows = await getManifestRows('job-1')

    expect(rows).toHaveLength(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('does not fall back when manifest/view fails with a non-404 response', async () => {
    fetchMock.mockResolvedValueOnce(makeJsonResponse({ detail: 'boom' }, 500))

    await expect(getManifestRows('job-1')).rejects.toThrow('boom')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
