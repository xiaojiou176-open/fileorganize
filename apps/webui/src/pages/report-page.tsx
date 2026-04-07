import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { getJob, getManifestRows, getReport } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { useI18n } from '@/lib/i18n'
import type { Job, JobSummary, ManifestRow } from '@/lib/types'
import { createRouteIntentPrefetchHandlers } from '@/routes/lazy-routes'

const ReportChartsGrid = lazy(() => import('@/components/report/report-charts-grid').then((module) => ({ default: module.ReportChartsGrid })))

function ChartGridSkeleton() {
  return (
    <>
      {Array.from({ length: 4 }, (_, index) => (
        <Card key={index}>
          <CardHeader className="pb-3">
            <Skeleton className="h-4 w-28" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-56 w-full rounded-xl" />
          </CardContent>
        </Card>
      ))}
    </>
  )
}

export function ReportPage() {
  const { t } = useI18n()
  const { jobId = '' } = useParams()
  const [job, setJob] = useState<Job | null>(null)
  const [summary, setSummary] = useState<JobSummary | null>(null)
  const [manifestRows, setManifestRows] = useState<ManifestRow[]>([])
  const [errorMessage, setErrorMessage] = useState('')
  const [searchParams, setSearchParams] = useSearchParams()
  const reviewPrefetch = createRouteIntentPrefetchHandlers('review')

  useEffect(() => {
    let mounted = true

    async function loadData() {
      try {
        const [nextJob, nextSummary, nextRows] = await Promise.all([getJob(jobId), getReport(jobId), getManifestRows(jobId)])
        if (mounted) {
          setJob(nextJob ?? null)
          setSummary(nextSummary)
          setManifestRows(nextRows)
          setErrorMessage('')
        }
      } catch (error) {
        if (mounted) {
          setJob(null)
          setSummary(null)
          setManifestRows([])
          setErrorMessage(error instanceof Error ? error.message : t('report.toast.loadFailed'))
        }
      }
    }

    void loadData()
    return () => {
      mounted = false
    }
  }, [jobId, t])

  const q = searchParams.get('q') ?? ''
  const category = searchParams.get('category') ?? ''
  const media = searchParams.get('media') ?? ''
  const status = searchParams.get('status') ?? ''
  const error = searchParams.get('error') ?? ''

  function setFilter(key: 'q' | 'category' | 'media' | 'status' | 'error', value: string) {
    const next = new URLSearchParams(searchParams)
    const current = key === 'q' ? q : key === 'category' ? category : key === 'media' ? media : key === 'status' ? status : error
    if (!value || value === current) {
      next.delete(key)
    } else {
      next.set(key, value)
    }
    setSearchParams(next, { replace: true })
  }

  function clearAllFilters() {
    const next = new URLSearchParams(searchParams)
    next.delete('q')
    next.delete('category')
    next.delete('media')
    next.delete('status')
    next.delete('error')
    setSearchParams(next, { replace: true })
  }

  const categoryData = useMemo(() => Object.entries(summary?.by_category ?? {}).map(([name, value]) => ({ name, value })), [summary])
  const mediaTypeData = useMemo(() => Object.entries(summary?.by_media_type ?? {}).map(([name, value]) => ({ name, value })), [summary])
  const errorCodeData = useMemo(() => Object.entries(summary?.error_codes ?? {}).map(([name, value]) => ({ name, value })), [summary])
  const statusData = useMemo(() => Object.entries(summary?.by_status ?? {}).map(([name, value]) => ({ name, value })), [summary])

  const filteredRows = useMemo(() => {
    return manifestRows.filter((row) => {
      const matchQuery =
        q.trim().length === 0 ||
        [row.file_name, row.category, row.status, row.error_code, row.media_type, row.title].join(' ').toLowerCase().includes(q.toLowerCase())
      const matchCategory = category.length === 0 || row.category === category
      const matchMedia = media.length === 0 || row.media_type === media
      const matchStatus = status.length === 0 || row.status === status
      const matchError = error.length === 0 || row.error_code === error
      return matchQuery && matchCategory && matchMedia && matchStatus && matchError
    })
  }, [category, error, manifestRows, media, q, status])

  const rowsWithLearning = useMemo(
    () => manifestRows.filter((row) => (row.learned_suggestions?.length ?? 0) > 0).length,
    [manifestRows],
  )
  const reviewBuckets = summary?.by_review_bucket
  const needsReviewCount = reviewBuckets?.needs_review ?? 0
  const conflictCount = reviewBuckets?.conflict ?? 0
  const blockedCount = reviewBuckets?.blocked ?? 0

  return (
    <div className="space-y-6">
      <Card className="border-primary/20 bg-primary/5">
        <CardHeader>
          <CardTitle>{t('report.hero.title')}</CardTitle>
          <CardDescription>{t('report.hero.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
            {conflictCount > 0 ? <Badge variant="warning">{t('report.hero.conflictCount', { count: conflictCount })}</Badge> : null}
            {blockedCount > 0 ? <Badge variant="destructive">{t('report.hero.blockedCount', { count: blockedCount })}</Badge> : null}
            {needsReviewCount > 0 ? <Badge variant="secondary">{t('report.hero.needsReviewCount', { count: needsReviewCount })}</Badge> : null}
            {rowsWithLearning > 0 ? <Badge variant="outline">{t('report.hero.learningCount', { count: rowsWithLearning })}</Badge> : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {conflictCount > 0 ? (
              <Button asChild>
                <Link {...reviewPrefetch} to={`/review/${jobId}?from=report&bucket=conflict`}>
                  {t('report.hero.reviewConflicts')}
                </Link>
              </Button>
            ) : null}
            {needsReviewCount > 0 ? (
              <Button asChild variant="outline">
                <Link {...reviewPrefetch} to={`/review/${jobId}?from=report&bucket=needs_review`}>
                  {t('report.hero.reviewHumanRows')}
                </Link>
              </Button>
            ) : null}
            {rowsWithLearning > 0 ? (
              <Button asChild variant="outline">
                <Link {...reviewPrefetch} to={`/review/${jobId}?from=report&learned=1`}>
                  {t('report.hero.reviewLearned')}
                </Link>
              </Button>
            ) : null}
          </div>
          <p className="text-xs text-muted-foreground">{t('report.hero.footer')}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('report.insights.title')}</CardTitle>
          <CardDescription>{t('report.insights.description', { jobId: job?.id ?? jobId })}</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Suspense fallback={<ChartGridSkeleton />}>
            {errorMessage ? (
              <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
                <p>{errorMessage}</p>
                <div className="mt-3">
                  <Button
                    onClick={() => {
                      window.location.reload()
                    }}
                    size="sm"
                    variant="outline"
                  >
                    {t('report.insights.retry')}
                  </Button>
                </div>
              </div>
            ) : (
              <ReportChartsGrid
                activeFilters={{ category, error, media, status }}
                categoryData={categoryData}
                errorCodeData={errorCodeData}
                mediaTypeData={mediaTypeData}
                onSelectFilter={setFilter}
                statusData={statusData}
              />
            )}
          </Suspense>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('report.filters.title')}</CardTitle>
          <CardDescription>{t('report.filters.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {summary?.by_review_bucket ? (
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">{t('report.filters.autoSafe', { count: summary.by_review_bucket.auto_safe ?? 0 })}</Badge>
              <Badge variant="outline">{t('report.filters.needsReview', { count: summary.by_review_bucket.needs_review ?? 0 })}</Badge>
              <Badge variant="outline">{t('report.filters.conflict', { count: summary.by_review_bucket.conflict ?? 0 })}</Badge>
              <Badge variant="outline">{t('report.filters.blocked', { count: summary.by_review_bucket.blocked ?? 0 })}</Badge>
              {typeof summary.collection_count === 'number' ? <Badge variant="outline">{t('report.filters.collections', { count: summary.collection_count })}</Badge> : null}
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Input
              onChange={(event) => {
                setFilter('q', event.target.value)
              }}
              placeholder={t('report.filters.placeholder')}
              value={q}
            />
            <Button onClick={clearAllFilters} size="sm" variant="outline">
              {t('report.filters.clear')}
            </Button>
          </div>

          <div className="flex flex-wrap gap-2">
            {category ? <Badge variant="secondary">category={category}</Badge> : null}
            {media ? <Badge variant="secondary">media={media}</Badge> : null}
            {status ? <Badge variant="secondary">status={status}</Badge> : null}
            {error ? <Badge variant="secondary">error={error}</Badge> : null}
            {q ? <Badge variant="outline">q={q}</Badge> : null}
            <Badge variant="outline">{t('report.filters.results', { count: filteredRows.length })}</Badge>
          </div>

          <div className="grid grid-cols-1 gap-2">
            {filteredRows.map((row) => (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border p-3" key={row.id}>
                <div>
                  <p className="text-sm font-medium">{row.file_name}</p>
                  <p className="text-xs text-muted-foreground">{row.title}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline">{row.category}</Badge>
                  <Badge variant="outline">{row.media_type}</Badge>
                  <Badge variant={row.status === 'error' ? 'destructive' : 'secondary'}>{row.status}</Badge>
                  {row.error_code ? <Badge variant="warning">{row.error_code}</Badge> : null}
                </div>
              </div>
            ))}
            {filteredRows.length === 0 ? <p className="rounded-xl border border-border p-4 text-sm text-muted-foreground">{t('report.filters.empty')}</p> : null}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
