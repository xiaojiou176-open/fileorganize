import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { listStrategyPacks, listWatchSources, scanInbox, startInboxAnalyze, upsertWatchSource } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import type { InboxBatch, StrategyPack, WatchSource } from '@/lib/types'
import { createRouteIntentPrefetchHandlers } from '@/routes/lazy-routes'

export function InboxPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [watchSources, setWatchSources] = useState<WatchSource[]>([])
  const [strategyPacks, setStrategyPacks] = useState<StrategyPack[]>([])
  const [batches, setBatches] = useState<InboxBatch[]>([])
  const [name, setName] = useState('')
  const [inputRoot, setInputRoot] = useState('')
  const [strategyPackId, setStrategyPackId] = useState('')
  const [launchingBatchId, setLaunchingBatchId] = useState('')
  const analyzePrefetch = createRouteIntentPrefetchHandlers('analyze')
  const reviewPrefetch = createRouteIntentPrefetchHandlers('review')

  const selectedPack = useMemo(
    () => strategyPacks.find((pack) => pack.id === strategyPackId) ?? null,
    [strategyPackId, strategyPacks],
  )

  function buildAnalyzeSearch(inputRootValue: string, packId?: string, batchId?: string, watchSourceId?: string) {
    const params = new URLSearchParams()
    params.set('source', 'inbox')
    params.set('inputRoot', inputRootValue)
    if (packId) {
      params.set('strategyPack', packId)
    }
    if (batchId) {
      params.set('batchId', batchId)
    }
    if (watchSourceId) {
      params.set('watchSourceId', watchSourceId)
    }
    return params.toString()
  }

  const refresh = useCallback(async () => {
    try {
      const [nextSources, nextPacks] = await Promise.all([listWatchSources(), listStrategyPacks()])
      setWatchSources(nextSources)
      setStrategyPacks(nextPacks.items)
      setStrategyPackId((prev) => prev || nextPacks.items[0]?.id || '')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('inbox.toast.loadFailed'))
    }
  }, [t])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refresh()
    }, 0)
    return () => {
      window.clearTimeout(timer)
    }
  }, [refresh])

  async function handleAdd() {
    try {
      const next = await upsertWatchSource({
        name,
        input_root: inputRoot,
        enabled: true,
        strategy_pack_id: strategyPackId,
      })
      setWatchSources((prev) => [...prev, next])
      setName('')
      setInputRoot('')
      toast.success(t('inbox.toast.watchSourceSaved'))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('inbox.toast.watchSourceSaveFailed'))
    }
  }

  async function handleScan() {
    try {
      const next = await scanInbox()
      setBatches(next)
      toast.success(t('inbox.toast.scanSuccess', { count: next.length }))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('inbox.toast.scanFailed'))
    }
  }

  async function handleLaunchAnalyze(batch: InboxBatch) {
    setLaunchingBatchId(batch.id)
    try {
      const response = await startInboxAnalyze({
        watchSourceId: batch.watch_source_id,
        strategyPackId: batch.strategy_pack_id,
      })
      toast.success(
        t('inbox.toast.launchAnalyzeSuccess', {
          name: response.batch.source_name || batch.source_name || batch.id,
        }),
      )
      const params = new URLSearchParams(
        buildAnalyzeSearch(
          response.batch.input_root || batch.input_root,
          response.batch.strategy_pack_id || batch.strategy_pack_id,
          response.batch.id || batch.id,
          response.batch.watch_source_id || batch.watch_source_id,
        ),
      )
      params.set('jobId', response.job_id)
      navigate(`/analyze?${params.toString()}`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('inbox.toast.launchAnalyzeFailed'))
    } finally {
      setLaunchingBatchId('')
    }
  }

  return (
    <div className="space-y-6">
      <Card className="border-primary/20 bg-primary/5">
        <CardHeader>
          <CardTitle>{t('inbox.hero.title')}</CardTitle>
          <CardDescription>{t('inbox.hero.description')}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2 text-sm text-muted-foreground">
          <Badge variant="outline">{t('inbox.hero.step.saveSource')}</Badge>
          <Badge variant="outline">{t('inbox.hero.step.scanBatch')}</Badge>
          <Badge variant="outline">{t('inbox.hero.step.startAnalyze')}</Badge>
          <Badge variant="outline">{t('inbox.hero.step.openReview')}</Badge>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('inbox.card.title')}</CardTitle>
          <CardDescription>{t('inbox.card.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-4">
            <Input onChange={(event) => setName(event.target.value)} placeholder={t('inbox.field.sourceName')} value={name} />
            <Input onChange={(event) => setInputRoot(event.target.value)} placeholder={t('inbox.field.inputRoot')} value={inputRoot} />
            <Select onValueChange={setStrategyPackId} value={strategyPackId}>
              {strategyPacks.map((pack) => (
                <option key={pack.id} value={pack.id}>
                  {pack.name}
                </option>
              ))}
            </Select>
            <Button onClick={() => void handleAdd()}>{t('inbox.cta.saveSource')}</Button>
          </div>
          {selectedPack ? (
            <div className="rounded-xl border border-border bg-card p-4">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-medium">{selectedPack.name}</p>
                <Badge variant="secondary">{t('inbox.pack.templateOnly')}</Badge>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                {selectedPack.description || t('inbox.pack.defaultDescription')}
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                <Badge variant="outline">{t('inbox.pack.model', { value: selectedPack.model || t('inbox.pack.keepCurrentDefault') })}</Badge>
                <Badge variant="outline">{t('inbox.pack.workers', { value: selectedPack.workers })}</Badge>
                <Badge variant="outline">{t('inbox.pack.categories', { value: selectedPack.categories.join(', ') || t('inbox.pack.none') })}</Badge>
                <Badge variant="outline">{t('inbox.pack.reviewThreshold', { value: Math.round(selectedPack.review_confidence_threshold * 100) })}</Badge>
              </div>
              <p className="mt-3 text-xs text-muted-foreground">{t('inbox.pack.explainer')}</p>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('inbox.sources.title')}</CardTitle>
          <CardDescription>{t('inbox.sources.description')}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          {watchSources.map((source) => (
            <div className="rounded-xl border border-border p-3" key={source.id}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-medium">{source.name}</p>
                  <p className="text-sm text-muted-foreground">{source.input_root}</p>
                  {source.strategy_pack_id ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {t('inbox.sources.strategyPack', {
                        value: strategyPacks.find((pack) => pack.id === source.strategy_pack_id)?.name ?? source.strategy_pack_id,
                      })}
                    </p>
                  ) : null}
                </div>
                <Button asChild size="sm" variant="outline">
                  <Link
                    {...analyzePrefetch}
                    to={`/analyze?${buildAnalyzeSearch(source.input_root, source.strategy_pack_id, undefined, source.id)}`}
                  >
                    {t('inbox.sources.startAnalyze')}
                  </Link>
                </Button>
              </div>
            </div>
          ))}
          {watchSources.length === 0 ? <p className="rounded-xl border border-border p-4 text-sm text-muted-foreground">{t('inbox.sources.empty')}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('inbox.scan.title')}</CardTitle>
          <CardDescription>{t('inbox.scan.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button onClick={() => void handleScan()} variant="outline">
            {t('inbox.scan.cta')}
          </Button>
          {batches.map((batch) => (
            <div className="rounded-xl border border-border p-3" key={batch.id}>
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-medium">{batch.source_name || batch.id}</p>
                <Badge variant="outline">{t('inbox.scan.fileCount', { count: batch.file_count })}</Badge>
                {batch.strategy_pack?.name ? <Badge variant="secondary">{batch.strategy_pack.name}</Badge> : null}
              </div>
              <p className="text-sm text-muted-foreground">{batch.input_root}</p>
              {batch.strategy_pack ? (
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span>{t('inbox.pack.model', { value: batch.analyze_defaults?.model || batch.strategy_pack.model || t('inbox.pack.defaultModel') })}</span>
                  <span>{t('inbox.pack.workers', { value: batch.analyze_defaults?.workers ?? batch.strategy_pack.workers })}</span>
                  <span>{t('inbox.pack.reviewThreshold', { value: Math.round((batch.strategy_pack.review_confidence_threshold ?? 0.8) * 100) })}</span>
                </div>
              ) : null}
              {batch.analyze_defaults?.categories ? (
                <p className="mt-2 text-xs text-muted-foreground">{t('inbox.scan.categories', { value: batch.analyze_defaults.categories })}</p>
              ) : null}
              {batch.strategy_pack?.default_template_patterns?.length ? (
                <p className="mt-2 text-xs text-muted-foreground">
                  {t('inbox.scan.namingTemplatePreview', { value: batch.strategy_pack.default_template_patterns[0] })}
                </p>
              ) : null}
              <div className="mt-3 flex flex-wrap gap-2">
                <Button disabled={launchingBatchId === batch.id} onClick={() => void handleLaunchAnalyze(batch)} size="sm">
                  {launchingBatchId === batch.id ? t('inbox.scan.launching') : t('inbox.scan.analyzeThisBatch')}
                </Button>
                <Button asChild size="sm" variant="outline">
                  <Link
                    {...analyzePrefetch}
                    to={`/analyze?${buildAnalyzeSearch(
                      batch.input_root,
                      strategyPackId || watchSources.find((source) => source.id === batch.watch_source_id)?.strategy_pack_id,
                      batch.id,
                      batch.watch_source_id,
                    )}`}
                  >
                    {t('inbox.scan.openChecklist')}
                  </Link>
                </Button>
                {batch.analyze_job_id ? (
                  <Button asChild size="sm" variant="outline">
                    <Link {...reviewPrefetch} to={`/review/${batch.analyze_job_id}`}>
                      {t('inbox.scan.openReviewQueue')}
                    </Link>
                  </Button>
                ) : null}
              </div>
            </div>
          ))}
          {batches.length > 0 ? (
            <p className="text-xs text-muted-foreground">{t('inbox.scan.footer')}</p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
