import { ArrowRight, Binary, Bot, CircleAlert, FolderOpen, KeyRound, NotebookText, PlayCircle, PlugZap, Rocket } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableWrapper } from '@/components/ui/table'
import { getRuntimeSettings, listJobs, type RuntimeSettings } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import type { Job } from '@/lib/types'
import { createRouteIntentPrefetchHandlers } from '@/routes/lazy-routes'
import { formatDate, progressToPercent } from '@/lib/utils'

const DASHBOARD_DOC_LINKS = {
  codex: 'https://github.com/xiaojiou176-open/movi-organizer/blob/main/docs/codex_mcp.md',
  claude: 'https://github.com/xiaojiou176-open/movi-organizer/blob/main/docs/claude_code_mcp.md',
  mcp: 'https://github.com/xiaojiou176-open/movi-organizer/blob/main/docs/mcp.md',
  developerGuide: 'https://github.com/xiaojiou176-open/movi-organizer/blob/main/docs/developer_guide.md',
} as const

export function DashboardPage() {
  const { t } = useI18n()
  const [jobs, setJobs] = useState<Job[]>([])
  const [runtimeSettings, setRuntimeSettings] = useState<RuntimeSettings | null>(null)

  useEffect(() => {
    let mounted = true

    async function loadJobs() {
      const [nextJobs, nextSettings] = await Promise.all([listJobs(), getRuntimeSettings()])
      if (mounted) {
        setJobs(nextJobs)
        setRuntimeSettings(nextSettings)
      }
    }

    void loadJobs()
    return () => {
      mounted = false
    }
  }, [])

  const pendingFiles = useMemo(() => jobs.find((job) => job.kind === 'analyze')?.summary?.total ?? 0, [jobs])
  const analyzeJobId = jobs.find((job) => job.kind === 'analyze')?.id ?? ''
  const dryRunWaiting = useMemo(
    () => jobs.filter((job) => job.kind === 'apply' && job.summary?.dry_run === true && job.status !== 'succeeded').length,
    [jobs],
  )
  const succeededJobs = useMemo(() => jobs.filter((job) => job.status === 'succeeded').length, [jobs])
  const reportJob = jobs.find((job) => job.report_path)
  const rollbackJobId = jobs.find((job) => job.kind === 'rollback')?.id ?? ''
  const analyzePrefetch = createRouteIntentPrefetchHandlers('analyze')
  const reviewPrefetch = createRouteIntentPrefetchHandlers('review')
  const applyPrefetch = createRouteIntentPrefetchHandlers('apply')
  const rollbackPrefetch = createRouteIntentPrefetchHandlers('rollback')
  const jobsPrefetch = createRouteIntentPrefetchHandlers('jobs')
  const setupPrefetch = createRouteIntentPrefetchHandlers('setup')

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-3xl border border-border/70 bg-[linear-gradient(135deg,hsl(var(--brand-soft))_0%,hsl(var(--card))_55%,hsl(var(--accent)/0.6)_100%)] p-6 shadow-card sm:p-8">
        <div className="pointer-events-none absolute -right-20 -top-16 h-56 w-56 rounded-full bg-primary/10 blur-3xl" />
        <div className="max-w-3xl space-y-4">
          <Badge variant={runtimeSettings?.ready ? 'success' : 'secondary'}>
            {runtimeSettings?.ready ? t('dashboard.badge.ready') : t('dashboard.badge.setupRequired')}
          </Badge>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t('dashboard.hero.title')}</h1>
          <p className="text-sm text-muted-foreground sm:text-base">{t('dashboard.hero.description')}</p>
          <div className="flex flex-wrap gap-3">
            {runtimeSettings?.ready ? (
              <Button asChild>
                <Link {...analyzePrefetch} to="/analyze">
                  {t('dashboard.cta.startAnalyze')}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            ) : (
              <Button asChild>
                <Link {...setupPrefetch} to="/setup">
                  {t('dashboard.cta.completeSetup')}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            )}
            {analyzeJobId ? (
              <Button asChild variant="outline">
                <Link {...reviewPrefetch} to={`/review/${analyzeJobId}`}>
                  {t('dashboard.cta.openReview')}
                </Link>
              </Button>
            ) : (
              <Button disabled variant="outline">
                {t('dashboard.cta.openReview')}
              </Button>
            )}
          </div>
        </div>
      </section>

      {!runtimeSettings?.ready ? (
        <Card className="border-primary/25 bg-primary/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <KeyRound className="h-4 w-4" />
              {t('dashboard.setupCard.title')}
            </CardTitle>
            <CardDescription>{t('dashboard.setupCard.description')}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <span>{t('dashboard.setupCard.missing', { items: runtimeSettings?.missing?.join(', ') || t('dashboard.setupCard.loading') })}</span>
            <Button asChild size="sm">
              <Link {...setupPrefetch} to="/setup">
                {t('dashboard.setupCard.openSetup')}
              </Link>
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>{t('dashboard.metrics.pendingFiles')}</CardDescription>
            <CardTitle className="text-2xl">{pendingFiles}</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{t('dashboard.metrics.pendingFilesHint')}</span>
            <FolderOpen className="h-4 w-4" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>{t('dashboard.metrics.pendingDryRunReview')}</CardDescription>
            <CardTitle className="text-2xl">{dryRunWaiting}</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{t('dashboard.metrics.pendingDryRunHint')}</span>
            <CircleAlert className="h-4 w-4 text-warning-ink" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>{t('dashboard.metrics.successfulJobs')}</CardDescription>
            <CardTitle className="text-2xl">{succeededJobs}</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{t('dashboard.metrics.successfulJobsHint')}</span>
            <Rocket className="h-4 w-4" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>{t('dashboard.metrics.latestReport')}</CardDescription>
            <CardTitle className="text-2xl">{reportJob ? reportJob.id.slice(-6) : 'r-113'}</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{t('dashboard.metrics.latestReportHint')}</span>
            <NotebookText className="h-4 w-4" />
          </CardContent>
        </Card>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.7fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>{t('dashboard.recentJobs.title')}</CardTitle>
            <CardDescription>{t('dashboard.recentJobs.description')}</CardDescription>
          </CardHeader>
          <CardContent>
            <TableWrapper>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Job ID</TableHead>
                    <TableHead>Kind</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Progress</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {jobs.map((job) => (
                    <TableRow key={job.id}>
                      <TableCell className="max-w-[220px] truncate font-medium">{job.id}</TableCell>
                      <TableCell>{job.kind}</TableCell>
                      <TableCell>
                        <Badge variant={job.status === 'succeeded' ? 'success' : job.status === 'failed' ? 'destructive' : 'secondary'}>
                          {job.status}
                        </Badge>
                      </TableCell>
                      <TableCell>{progressToPercent(job.progress)}%</TableCell>
                      <TableCell>{formatDate(job.started_at)}</TableCell>
                      <TableCell className="text-right">
                        <Button asChild size="sm" variant="ghost">
                          <Link {...reviewPrefetch} to={`/review/${job.id}`}>
                            View
                          </Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableWrapper>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t('dashboard.quickActions.title')}</CardTitle>
              <CardDescription>{t('dashboard.quickActions.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {!runtimeSettings?.ready ? (
                <Button asChild className="w-full justify-between">
                  <Link {...setupPrefetch} to="/setup">
                    {t('dashboard.cta.completeSetup')}
                    <KeyRound className="h-4 w-4" />
                  </Link>
                </Button>
              ) : null}
              <Button asChild className="w-full justify-between" variant="secondary">
                <Link {...analyzePrefetch} to="/analyze">
                  {t('dashboard.quickActions.guidedFlow')}
                  <PlayCircle className="h-4 w-4" />
                </Link>
              </Button>
              {analyzeJobId ? (
                <Button asChild className="w-full justify-between" variant="outline">
                  <Link {...applyPrefetch} to={`/apply/${analyzeJobId}`}>
                    {t('dashboard.quickActions.applyDryRun')}
                  </Link>
                </Button>
              ) : (
                <Button className="w-full justify-between" disabled variant="outline">
                  {t('dashboard.quickActions.applyDryRun')}
                </Button>
              )}
              {rollbackJobId ? (
                <Button asChild className="w-full justify-between" variant="outline">
                  <Link {...rollbackPrefetch} to={`/rollback/${rollbackJobId}`}>
                    {t('dashboard.quickActions.rollbackGuard')}
                  </Link>
                </Button>
              ) : (
                <Button className="w-full justify-between" disabled variant="outline">
                  {t('dashboard.quickActions.rollbackGuard')}
                </Button>
              )}
              <Button asChild className="w-full justify-between" variant="outline">
                <Link {...jobsPrefetch} to="/jobs">
                  {t('dashboard.quickActions.jobsHistory')}
                </Link>
              </Button>
              <p className="text-xs text-muted-foreground">{t('dashboard.quickActions.lastSynced', { time: formatDate(new Date().toISOString()) })}</p>
            </CardContent>
          </Card>

          <Card className="border-border/80 bg-card/95">
            <CardHeader>
              <CardTitle>{t('dashboard.builder.title')}</CardTitle>
              <CardDescription>{t('dashboard.builder.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="space-y-1">
                    <p className="font-medium">{t('dashboard.builder.ai.title')}</p>
                    <p className="text-sm text-muted-foreground">{t('dashboard.builder.ai.description')}</p>
                  </div>
                  <Bot className="h-5 w-5 text-primary" />
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge variant="outline">{t('dashboard.builder.badge.reviewSafe')}</Badge>
                  <Badge variant="outline">{runtimeSettings?.model || 'gemini-3-flash-preview'}</Badge>
                </div>
              </div>

              <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="space-y-1">
                    <p className="font-medium">{t('dashboard.builder.mcp.title')}</p>
                    <p className="text-sm text-muted-foreground">{t('dashboard.builder.mcp.description')}</p>
                  </div>
                  <PlugZap className="h-5 w-5 text-primary" />
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge variant="outline">{t('dashboard.builder.badge.localFirst')}</Badge>
                  <Badge variant="outline">{t('dashboard.builder.badge.reviewSafe')}</Badge>
                </div>
              </div>

              <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="space-y-1">
                    <p className="font-medium">{t('dashboard.builder.api.title')}</p>
                    <p className="text-sm text-muted-foreground">{t('dashboard.builder.api.description')}</p>
                  </div>
                  <Binary className="h-5 w-5 text-primary" />
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge variant="outline">OpenAPI</Badge>
                  <Badge variant="outline">generated client</Badge>
                </div>
              </div>

              <div className="rounded-2xl border border-border/70 bg-muted/30 p-4">
                <p className="font-medium">{t('dashboard.builder.pack.title')}</p>
                <p className="mt-1 text-sm text-muted-foreground">{t('dashboard.builder.pack.description')}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge variant="outline">{t('dashboard.builder.badge.templateOnly')}</Badge>
                  <Badge variant="outline">
                    {runtimeSettings?.active_strategy_pack_id
                      ? t('dashboard.builder.pack.current', { packId: runtimeSettings.active_strategy_pack_id })
                      : t('dashboard.builder.pack.none')}
                  </Badge>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button asChild size="sm" variant="outline">
                  <a href={DASHBOARD_DOC_LINKS.codex} rel="noreferrer" target="_blank">
                    {t('dashboard.builder.link.codex')}
                  </a>
                </Button>
                <Button asChild size="sm" variant="outline">
                  <a href={DASHBOARD_DOC_LINKS.claude} rel="noreferrer" target="_blank">
                    {t('dashboard.builder.link.claude')}
                  </a>
                </Button>
                <Button asChild size="sm" variant="outline">
                  <a href={DASHBOARD_DOC_LINKS.mcp} rel="noreferrer" target="_blank">
                    {t('dashboard.builder.link.mcp')}
                  </a>
                </Button>
                <Button asChild size="sm" variant="outline">
                  <a href={DASHBOARD_DOC_LINKS.developerGuide} rel="noreferrer" target="_blank">
                    {t('dashboard.builder.link.devGuide')}
                  </a>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  )
}
