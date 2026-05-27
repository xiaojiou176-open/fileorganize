import { useCallback, useEffect, useRef, useState } from 'react'

import { listJobs, subscribeJobs } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import type { Job, JobsQuery } from '@/lib/types'

type LiveState = 'connecting' | 'open' | 'error' | 'unsupported' | 'closed'

export function useLiveJobs(query?: JobsQuery) {
  const { t } = useI18n()
  const [jobs, setJobs] = useState<Job[]>([])
  const [state, setState] = useState<LiveState>('connecting')
  const [error, setError] = useState<string>('')
  const refreshTimerRef = useRef<number | null>(null)

  const refresh = useCallback(async () => {
    try {
      const next = await listJobs(query)
      setJobs(next)
      setError('')
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : t('liveJobs.refreshFailed'))
    }
  }, [query, t])

  const scheduleRefresh = useCallback(() => {
    if (refreshTimerRef.current !== null) {
      return
    }
    refreshTimerRef.current = window.setTimeout(() => {
      refreshTimerRef.current = null
      void refresh()
    }, 280)
  }, [refresh])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refresh()
    }, 0)
    return () => {
      window.clearTimeout(timer)
    }
  }, [refresh])

  useEffect(() => {
    const unsubscribe = subscribeJobs({
      onState: (nextState) => {
        setState(nextState)
      },
      onMessage: () => {
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
  }, [scheduleRefresh])

  return {
    jobs,
    state,
    error,
    refresh,
  }
}
