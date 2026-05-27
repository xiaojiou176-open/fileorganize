import { AlertCircle, CheckCircle2, Clock3, LoaderCircle, XCircle } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { LogPanel } from '@/components/observability/log-panel'
import { useLiveJob } from '@/hooks/use-live-job'
import type { Job } from '@/lib/types'
import { formatDate, progressToPercent } from '@/lib/utils'
import { createRouteIntentPrefetchHandlers } from '@/routes/lazy-routes'

interface JobCenterSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  jobs: Job[]
  streamState: 'connecting' | 'open' | 'error' | 'unsupported' | 'closed'
}

const statusMap = {
  queued: { icon: Clock3, tone: 'secondary' as const, label: 'Queued' },
  running: { icon: LoaderCircle, tone: 'secondary' as const, label: 'Running' },
  cancelling: { icon: LoaderCircle, tone: 'warning' as const, label: 'Cancelling' },
  succeeded: { icon: CheckCircle2, tone: 'success' as const, label: 'Succeeded' },
  failed: { icon: XCircle, tone: 'destructive' as const, label: 'Failed' },
  cancelled: { icon: AlertCircle, tone: 'outline' as const, label: 'Cancelled' },
}

export function JobCenterSheet({ open, onOpenChange, jobs, streamState }: JobCenterSheetProps) {
  const [query, setQuery] = useState('')
  const [activeJobId, setActiveJobId] = useState<string>('')

  const visible = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    return jobs.filter((job) => {
      if (keyword.length === 0) {
        return true
      }
      return `${job.id} ${job.kind} ${job.status}`.toLowerCase().includes(keyword)
    })
  }, [jobs, query])

  const selectedJobId = activeJobId || visible[0]?.id || ''
  const selectedJob = jobs.find((job) => job.id === selectedJobId) ?? null
  const { events, state, refresh } = useLiveJob(selectedJobId, selectedJobId.length > 0 && open)
  const reviewPrefetch = createRouteIntentPrefetchHandlers('review')
  const reportPrefetch = createRouteIntentPrefetchHandlers('report')
  const applyPrefetch = createRouteIntentPrefetchHandlers('apply')
  const rollbackPrefetch = createRouteIntentPrefetchHandlers('rollback')

  return (
    <Sheet onOpenChange={onOpenChange} open={open}>
      <SheetContent className="w-[min(94vw,980px)]">
        <SheetHeader>
          <SheetTitle>Job Center</SheetTitle>
          <SheetDescription>Subscribe to the job center over SSE, search job history, and inspect the full logs.</SheetDescription>
        </SheetHeader>

        <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Input onChange={(event) => setQuery(event.target.value)} placeholder="Search job id / kind / status" value={query} />
              <Badge variant={streamState === 'open' ? 'success' : 'warning'}>{streamState === 'open' ? 'Live' : 'Fallback'}</Badge>
            </div>

            <div className="max-h-[72vh] space-y-2 overflow-auto pr-1 md:max-h-[65vh]">
              {visible.map((job) => {
                const status = statusMap[job.status]
                const Icon = status.icon
                const active = job.id === selectedJobId
                return (
                  <Card className={active ? 'border-primary/60' : ''} key={job.id}>
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center justify-between text-sm">
                        <Button
                          className="h-10 max-w-full justify-start truncate px-3 text-left text-sm font-semibold"
                          onClick={() => setActiveJobId(job.id)}
                          type="button"
                          variant="ghost"
                        >
                          {job.id}
                        </Button>
                        <Badge variant={status.tone}>
                          <Icon className="mr-1 h-3.5 w-3.5" />
                          {status.label}
                        </Badge>
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 text-xs text-muted-foreground">
                      <p>
                        {job.kind.toUpperCase()} | {job.phase}
                      </p>
                      <p>Progress {progressToPercent(job.progress)}%</p>
                      <p>Started {formatDate(job.started_at)}</p>
                      {job.latest_error ? <p className="text-warning-ink">{job.latest_error}</p> : null}
                      <div className="flex flex-wrap gap-3 pt-1">
                        <Button asChild variant="outline">
                          <Link {...reviewPrefetch} to={`/review/${job.id}`}>
                            Review
                          </Link>
                        </Button>
                        <Button asChild variant="outline">
                          <Link {...reportPrefetch} to={`/report/${job.id}`}>
                            Report
                          </Link>
                        </Button>
                        <Button asChild>
                          <Link {...(job.kind === 'rollback' ? rollbackPrefetch : applyPrefetch)} to={job.kind === 'rollback' ? `/rollback/${job.id}` : `/apply/${job.id}`}>
                            Open
                          </Link>
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          </div>

          <div className="space-y-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Current job</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                {selectedJob ? (
                  <div className="space-y-1">
                    <p>{selectedJob.id}</p>
                    <p>
                      {selectedJob.kind.toUpperCase()} | {selectedJob.phase}
                    </p>
                  </div>
                ) : (
                  <p>No job selected.</p>
                )}
              </CardContent>
            </Card>

            <LogPanel
              connectionState={state}
              description="Filter log lines by level and copy them when needed."
              events={events}
              onRefresh={() => {
                void refresh()
              }}
              title="Job Logs"
            />
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
