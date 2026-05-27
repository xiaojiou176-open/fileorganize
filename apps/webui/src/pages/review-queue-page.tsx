import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'

import { CollectionPanel } from '@/components/review/collection-panel'
import { LearnedRulesPanel } from '@/components/review/learned-rules-panel'
import { createRuleDraftFromLearnedSuggestion, explainLearnedSuggestion } from '@/components/review/review-intelligence'
import { ReviewQueueSummary } from '@/components/review/review-queue-summary'
import { RuleStudioSheet, type RuleStudioDraft, type RuleStudioSeedMeta } from '@/components/review/rule-studio-sheet'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { applyReviewQueueBatchTriage, applyReviewRule, draftReviewRuleFromExamples, getReviewQueue, type ReviewQueuePayload } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import type { LearnedRule, ManifestRow } from '@/lib/types'
import { createRouteIntentPrefetchHandlers } from '@/routes/lazy-routes'

const BUCKET_ORDER = ['blocked', 'conflict', 'needs_review', 'auto_safe'] as const

type LoadState = 'loading' | 'ready' | 'error'
type TriageBucket = 'all' | (typeof BUCKET_ORDER)[number]

function findSuggestedBatchCategory(rows: ManifestRow[]): string {
  const counts = new Map<string, number>()
  for (const row of rows) {
    for (const suggestion of row.learned_suggestions ?? []) {
      if (suggestion.suggestion_type !== 'category') {
        continue
      }
      counts.set(suggestion.suggestion_value, (counts.get(suggestion.suggestion_value) ?? 0) + suggestion.count)
    }
  }
  const [suggestionValue] =
    [...counts.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], 'zh-Hans-CN'))[0] ?? []
  return suggestionValue ?? ''
}

function LoadingState() {
  const { t } = useI18n()
  return (
    <Card className="workspace-panel">
      <CardHeader>
        <CardTitle>{t('review.loading.title')}</CardTitle>
        <CardDescription>{t('review.loading.description')}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-2">
        <Skeleton className="h-24 rounded-xl" />
        <Skeleton className="h-24 rounded-xl" />
        <Skeleton className="h-40 rounded-xl md:col-span-2" />
      </CardContent>
    </Card>
  )
}

export function ReviewQueuePage() {
  const { t } = useI18n()
  const { jobId = '' } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [loadError, setLoadError] = useState('')
  const [payload, setPayload] = useState<ReviewQueuePayload | null>(null)
  const [selectedCollectionId, setSelectedCollectionId] = useState('')
  const [seedRule, setSeedRule] = useState<RuleStudioDraft | null>(null)
  const [seedRuleMeta, setSeedRuleMeta] = useState<RuleStudioSeedMeta | null>(null)
  const [seedRuleToken, setSeedRuleToken] = useState(0)
  const [triageBucket, setTriageBucket] = useState<TriageBucket>('needs_review')
  const [triageCategory, setTriageCategory] = useState('')
  const [triageApplying, setTriageApplying] = useState(false)
  const [exampleRowIds, setExampleRowIds] = useState<string[]>([])
  const [draftingExamples, setDraftingExamples] = useState(false)
  const focusedBucket = searchParams.get('bucket')
  const focusedCollectionId = searchParams.get('collection')
  const focusLearned = searchParams.get('learned') === '1'
  const focusSource = searchParams.get('from') ?? ''

  const effectiveFocusedBucket = focusedBucket && BUCKET_ORDER.includes(focusedBucket as (typeof BUCKET_ORDER)[number]) ? focusedBucket : ''

  const refreshQueue = useCallback(async () => {
    setLoadState('loading')
    setLoadError('')
    try {
      const next = await getReviewQueue(jobId)
      setPayload(next)
      setSelectedCollectionId((previous) => {
        if (previous && next.collections.some((collection) => collection.id === previous)) {
          return previous
        }
        return ''
      })
      setLoadState('ready')
    } catch (error) {
      setLoadState('error')
      const message = error instanceof Error ? error.message : t('review.error.fallback')
      setLoadError(message)
      toast.error(message)
    }
  }, [jobId, t])

  useEffect(() => {
    void refreshQueue()
  }, [refreshQueue])

  useEffect(() => {
    if (!payload) {
      return
    }
    if (focusedCollectionId && payload.collections.some((collection) => collection.id === focusedCollectionId)) {
      setSelectedCollectionId((previous) => previous || focusedCollectionId)
    }
  }, [focusedCollectionId, payload])

  useEffect(() => {
    if (effectiveFocusedBucket) {
      setTriageBucket(effectiveFocusedBucket as TriageBucket)
    }
  }, [effectiveFocusedBucket])

  const filteredRows = useMemo(() => {
    if (!payload) {
      return []
    }
    let rows = payload.rows
    const activeCollectionId = selectedCollectionId || focusedCollectionId || ''
    if (activeCollectionId) {
      rows = rows.filter((row) => row.collection_id === activeCollectionId)
    }
    if (effectiveFocusedBucket) {
      rows = rows.filter((row) => (row.review_bucket ?? 'needs_review') === effectiveFocusedBucket)
    }
    if (focusLearned) {
      rows = rows.filter((row) => (row.learned_suggestions?.length ?? 0) > 0)
    }
    return rows
  }, [effectiveFocusedBucket, focusLearned, focusedCollectionId, payload, selectedCollectionId])

  useEffect(() => {
    const validIds = new Set(filteredRows.map((row) => row.id))
    setExampleRowIds((previous) => previous.filter((rowId) => validIds.has(rowId)))
  }, [filteredRows])

  const rowsByBucket = useMemo(() => {
    const grouped = new Map<string, ManifestRow[]>()
    for (const row of filteredRows) {
      const bucket = row.review_bucket ?? 'needs_review'
      grouped.set(bucket, [...(grouped.get(bucket) ?? []), row])
    }
    return grouped
  }, [filteredRows])

  const triageRows = useMemo(() => {
    if (triageBucket === 'all') {
      return filteredRows
    }
    return filteredRows.filter((row) => (row.review_bucket ?? 'needs_review') === triageBucket)
  }, [filteredRows, triageBucket])

  const selectedCollectionTitle = useMemo(
    () => payload?.collections.find((collection) => collection.id === (selectedCollectionId || focusedCollectionId || ''))?.title ?? '',
    [focusedCollectionId, payload, selectedCollectionId],
  )

  const rowLookup = useMemo(() => new Map((payload?.rows ?? []).map((row) => [row.id, row])), [payload])
  const suggestedBatchCategory = useMemo(() => findSuggestedBatchCategory(triageRows), [triageRows])
  const copilotSummary = payload?.copilot_summary

  const exampleRows = useMemo(
    () => filteredRows.filter((row) => exampleRowIds.includes(row.id)),
    [exampleRowIds, filteredRows],
  )
  const exampleSelectionValid = exampleRows.length >= 2 && exampleRows.length <= 5

  const manifestPrefetch = createRouteIntentPrefetchHandlers('manifest')
  const conflictPrefetch = createRouteIntentPrefetchHandlers('conflicts')
  const applyPrefetch = createRouteIntentPrefetchHandlers('apply')
  const hasFocusFilters = Boolean(effectiveFocusedBucket || focusLearned || focusedCollectionId)

  function clearFocusFilters() {
    const next = new URLSearchParams(searchParams)
    next.delete('bucket')
    next.delete('learned')
    next.delete('collection')
    next.delete('from')
    if (focusedCollectionId && selectedCollectionId === focusedCollectionId) {
      setSelectedCollectionId('')
    }
    setSearchParams(next, { replace: true })
  }

  async function handleDraftFromExamples() {
    if (!exampleSelectionValid) {
      return
    }
    setDraftingExamples(true)
    try {
      const response = await draftReviewRuleFromExamples(
        jobId,
        exampleRows.map((row) => row.id),
      )
      setSeedRule(response.draft)
      setSeedRuleMeta({
        source: 'example-draft',
        title: 'Example draft loaded',
        description:
          'This draft came from the backend review examples route. It is draft-only and was not saved or applied for you.',
        warnings: [
          `Selected examples: ${response.selected_count}.`,
          response.save_allowed ? '' : 'Saving is still a manual choice in Rule Studio.',
          response.apply_allowed ? '' : 'Applying is still a manual overlay action in Rule Studio.',
          ...response.warnings,
          ...(response.draft.warnings ?? []),
        ].filter(Boolean),
      })
      setSeedRuleToken((previous) => previous + 1)
      toast.success(t('review.toast.loadedExampleDraft'))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('review.toast.failedDraftExamples'))
    } finally {
      setDraftingExamples(false)
    }
  }

  async function applyBatchTriage(input: { setCategory?: string; setIgnore?: boolean }, successMessage: string) {
    if (triageRows.length === 0) {
      return
    }
    setTriageApplying(true)
    try {
      const nextPayload = await applyReviewQueueBatchTriage(jobId, {
        rowIds: triageRows.map((row) => row.id),
        setCategory: input.setCategory,
        setIgnore: input.setIgnore,
      })
      setPayload(nextPayload)
      toast.success(t('review.toast.batchApplied', { message: successMessage, count: nextPayload.applied_count }))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('review.toast.batchTriageFailed'))
    } finally {
      setTriageApplying(false)
    }
  }

  async function handleAcceptLearnedRule(rule: LearnedRule) {
    try {
      const nextPayload = await applyReviewRule(jobId, undefined, createRuleDraftFromLearnedSuggestion(rule))
      setPayload(nextPayload)
      toast.success(t('review.toast.acceptedLearned'))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('review.toast.acceptLearnedFailed'))
    }
  }

  async function handleApplyBatchCategory() {
    const nextCategory = triageCategory.trim()
    if (!nextCategory || triageRows.length === 0) {
      return
    }
    await applyBatchTriage({ setCategory: nextCategory }, `Applied category "${nextCategory}" to the current scope`)
  }

  async function handleApplyBatchIgnore(value: boolean) {
    if (triageRows.length === 0) {
      return
    }
    await applyBatchTriage({ setIgnore: value }, `${value ? 'Ignored' : 'Restored'} the current scope in the review overlay`)
  }

  function handlePromoteDraft(draft: RuleStudioDraft, successMessage: string, meta?: RuleStudioSeedMeta | null) {
    setSeedRule(draft)
    setSeedRuleMeta(meta ?? null)
    setSeedRuleToken((previous) => previous + 1)
    toast.success(successMessage)
  }

  const showEmptyState = loadState === 'ready' && filteredRows.length === 0

  return (
    <div className="space-y-6">
      <Card className="workspace-panel overflow-hidden">
        <CardHeader>
          <CardTitle>{t('review.page.title')}</CardTitle>
          <CardDescription>{t('review.page.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">{t('review.batch.rows', { count: filteredRows.length })}</Badge>
            {selectedCollectionTitle ? <Badge variant="outline">{t('review.focus.collection', { value: selectedCollectionTitle })}</Badge> : null}
          </div>
          <div className="flex flex-wrap gap-3">
            <Button asChild variant="outline">
              <Link {...manifestPrefetch} to={`/manifest/${jobId}`}>
                {t('review.page.openManifest')}
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link {...conflictPrefetch} to={`/conflicts/${jobId}`}>
                {t('review.page.openConflict')}
              </Link>
            </Button>
            <Button asChild>
              <Link {...applyPrefetch} to={`/apply/${jobId}`}>
                {t('review.page.continueApply')}
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      {loadState === 'loading' ? <LoadingState /> : null}

      {loadState === 'error' ? (
        <Alert className="border-destructive/40 bg-destructive/10 text-destructive">
          <AlertTitle>{t('review.error.title')}</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-3">
            <span>{loadError || t('review.error.fallback')}</span>
            <Button onClick={() => void refreshQueue()} size="sm" type="button" variant="outline">
              {t('review.error.retry')}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {payload ? <ReviewQueueSummary summary={payload.summary} /> : null}

      {payload && hasFocusFilters ? (
        <Alert className="workspace-panel-soft border-primary/20 bg-primary/5">
          <AlertTitle>{focusSource === 'report' ? t('review.focus.fromReportTitle') : t('review.focus.scopeTitle')}</AlertTitle>
          <AlertDescription>
            {focusSource === 'report'
              ? t('review.focus.fromReportDescription')
              : t('review.focus.scopeDescription')}
          </AlertDescription>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {effectiveFocusedBucket ? <Badge variant="outline">{t('review.focus.bucket', { value: effectiveFocusedBucket })}</Badge> : null}
            {focusLearned ? <Badge variant="outline">{t('review.focus.learningOnly')}</Badge> : null}
            {selectedCollectionTitle ? <Badge variant="outline">{t('review.focus.collection', { value: selectedCollectionTitle })}</Badge> : null}
            <Button onClick={clearFocusFilters} size="sm" type="button" variant="outline">
              {t('review.focus.clear')}
            </Button>
          </div>
        </Alert>
      ) : null}

      {payload ? (
        <Card className="workspace-panel overflow-hidden">
          <CardHeader>
            <CardTitle>{t('review.copilot.title')}</CardTitle>
            <CardDescription>{t('review.copilot.description')}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6 xl:grid-cols-[minmax(0,1.18fr)_minmax(320px,0.82fr)]">
            <div className="space-y-4">
              <div className="rounded-[1.25rem] border border-border/70 bg-muted/20 p-5">
                <p className="workspace-kicker">{t('review.copilot.backendSummary')}</p>
                <p className="mt-3 text-xl font-semibold tracking-[-0.03em] text-foreground">{copilotSummary?.headline || t('review.copilot.noHeadline')}</p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {copilotSummary
                    ? t('review.copilot.withSummaryDescription')
                    : t('review.copilot.noSummaryDescription')}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {copilotSummary?.mode ? <Badge variant="secondary">{copilotSummary.mode}</Badge> : null}
                  <Badge variant="outline">{t('review.copilot.rowsInScope', { count: filteredRows.length })}</Badge>
                  <Badge variant="outline">{t('review.copilot.learnedRows', { count: filteredRows.filter((row) => (row.learned_suggestions?.length ?? 0) > 0).length })}</Badge>
                  {selectedCollectionTitle ? <Badge variant="outline">{t('review.copilot.collection', { value: selectedCollectionTitle })}</Badge> : null}
                  {copilotSummary ? <Badge variant="outline">{t('review.copilot.ruleOpportunities', { count: copilotSummary.rule_opportunities.length })}</Badge> : null}
                  {copilotSummary?.guardrails.review_only ? <Badge variant="outline">{t('review.copilot.reviewOnly')}</Badge> : null}
                  {copilotSummary?.guardrails.overlay_only ? <Badge variant="outline">{t('review.copilot.overlayOnly')}</Badge> : null}
                  {copilotSummary && !copilotSummary.guardrails.execute_allowed ? <Badge variant="outline">{t('review.copilot.executeDisabled')}</Badge> : null}
                </div>
              </div>

              {copilotSummary ? (
                <div className="grid gap-4 lg:grid-cols-3">
                  <div className="rounded-[1.2rem] border border-border/70 bg-card/70 p-4">
                    <p className="font-medium">{t('review.copilot.reasonsTitle')}</p>
                    <div className="mt-3 grid gap-3">
                      {copilotSummary.reasons.length === 0 ? (
                        <p className="text-sm text-muted-foreground">{t('review.copilot.noReasons')}</p>
                      ) : (
                        copilotSummary.reasons.map((reason) => (
                          <div className="rounded-[1rem] border border-border/70 bg-muted/20 p-3" key={reason.key}>
                            <div className="flex items-center justify-between gap-3">
                              <p className="text-sm font-medium">{reason.title}</p>
                              <Badge variant="outline">{reason.count}</Badge>
                            </div>
                            <p className="mt-2 text-sm text-muted-foreground">{reason.detail}</p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  <div className="rounded-[1.2rem] border border-border/70 bg-card/70 p-4">
                    <p className="font-medium">{t('review.copilot.prioritiesTitle')}</p>
                    <div className="mt-3 grid gap-3">
                      {copilotSummary.priorities.length === 0 ? (
                        <p className="text-sm text-muted-foreground">{t('review.copilot.noPriorities')}</p>
                      ) : (
                        copilotSummary.priorities.map((priority) => (
                          <div className="rounded-[1rem] border border-border/70 bg-muted/20 p-3" key={priority.row_id}>
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-sm font-medium">{priority.file_name}</p>
                              <Badge variant={priority.bucket === 'blocked' ? 'destructive' : priority.bucket === 'conflict' ? 'warning' : priority.bucket === 'auto_safe' ? 'success' : 'secondary'}>
                                {priority.bucket.replaceAll('_', ' ')}
                              </Badge>
                              <Badge variant="outline">{Math.round(priority.confidence * 100)}%</Badge>
                            </div>
                            <p className="mt-2 text-sm text-muted-foreground">{priority.reason}</p>
                            <p className="mt-1 text-sm text-muted-foreground">{t('review.copilot.suggestedAction', { value: priority.suggested_action })}</p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  <div className="rounded-[1.2rem] border border-border/70 bg-card/70 p-4">
                    <p className="font-medium">{t('review.copilot.ruleOpportunitiesTitle')}</p>
                    <div className="mt-3 grid gap-3">
                      {copilotSummary.rule_opportunities.length === 0 ? (
                        <p className="text-sm text-muted-foreground">{t('review.copilot.noRuleOpportunities')}</p>
                      ) : (
                        copilotSummary.rule_opportunities.map((opportunity) => (
                          <div className="rounded-[1rem] border border-border/70 bg-muted/20 p-3" key={opportunity.key}>
                            <div className="flex items-center justify-between gap-3">
                              <p className="text-sm font-medium">{opportunity.title}</p>
                              <Badge variant="outline">{opportunity.row_ids.length} row(s)</Badge>
                            </div>
                            <p className="mt-2 text-sm text-muted-foreground">{opportunity.reason}</p>
                            <p className="mt-1 text-sm text-muted-foreground">{t('review.copilot.suggestedAction', { value: opportunity.suggested_action })}</p>
                            <div className="mt-2">
                              <Button
                                onClick={() => setExampleRowIds(opportunity.row_ids.slice(0, 5))}
                                size="sm"
                                type="button"
                                variant="outline"
                              >
                                {t('review.copilot.useExampleSet')}
                              </Button>
                            </div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {opportunity.row_ids.slice(0, 3).map((rowId) => (
                                <Badge key={rowId} variant="secondary">
                                  {rowLookup.get(rowId)?.file_name ?? rowId}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                  <div className="rounded-[1.2rem] border border-border/70 bg-card/70 p-4 lg:col-span-3">
                    <p className="font-medium">{t('review.copilot.batchSuggestionsTitle')}</p>
                    <div className="mt-3 grid gap-3">
                      {copilotSummary.batch_triage.length === 0 ? (
                        <p className="text-sm text-muted-foreground">{t('review.copilot.noBatchSuggestions')}</p>
                      ) : (
                        copilotSummary.batch_triage.map((batch) => (
                          <div className="rounded-[1rem] border border-border/70 bg-muted/20 p-3" key={batch.id}>
                            <div className="flex items-center justify-between gap-3">
                              <p className="text-sm font-medium">{batch.label}</p>
                              <Badge variant="outline">{batch.count} row(s)</Badge>
                            </div>
                            <p className="mt-2 text-sm text-muted-foreground">{batch.reason}</p>
                            <p className="mt-1 text-sm text-muted-foreground">{t('review.copilot.nextStep', { value: batch.next_step })}</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <Button
                                onClick={() => setTriageBucket(batch.review_bucket as TriageBucket)}
                                size="sm"
                                type="button"
                                variant="outline"
                              >
                                {t('review.copilot.useTriageScope')}
                              </Button>
                              {batch.kind === 'collection' && batch.collection_id ? (
                                <Button
                                  onClick={() => setSelectedCollectionId(batch.collection_id ?? '')}
                                  size="sm"
                                  type="button"
                                  variant="ghost"
                                >
                                  {t('review.copilot.focusCollection')}
                                </Button>
                              ) : null}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              ) : null}

              <div className="rounded-[1.2rem] border border-border/70 bg-card/70 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-medium">{t('review.examples.title')}</p>
                    <p className="text-sm text-muted-foreground">{t('review.examples.description')}</p>
                  </div>
                  <Badge variant="outline">{t('review.examples.count', { count: exampleRows.length })}</Badge>
                </div>
                {exampleRows.length === 0 ? (
                    <p className="mt-3 rounded-[1rem] border border-border/70 bg-muted/20 p-3 text-sm text-muted-foreground">{t('review.examples.empty')}</p>
                ) : (
                  <div className="mt-3 space-y-3">
                    <div className="flex flex-wrap gap-2">
                      {exampleRows.map((row) => (
                        <Badge key={row.id} variant="secondary">
                          {row.file_name}
                        </Badge>
                      ))}
                    </div>
                    <p className="text-sm text-muted-foreground">{t('review.examples.currentSelection', { count: exampleRows.length })}</p>
                    {!exampleSelectionValid ? (
                      <p className="text-sm text-muted-foreground">{t('review.examples.selectionHint')}</p>
                    ) : null}
                  </div>
                )}
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button
                    disabled={!exampleSelectionValid || draftingExamples}
                    onClick={() => void handleDraftFromExamples()}
                    type="button"
                  >
                    {draftingExamples ? t('review.examples.drafting') : t('review.examples.generate')}
                  </Button>
                  <Button disabled={exampleRows.length === 0} onClick={() => setExampleRowIds([])} type="button" variant="ghost">
                    {t('review.examples.clear')}
                  </Button>
                </div>
              </div>
            </div>

            <div className="workspace-panel-soft xl:sticky xl:top-24 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="workspace-kicker">{t('review.batch.title')}</p>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">{t('review.batch.description')}</p>
                </div>
                <Badge variant="outline">{t('review.batch.rows', { count: triageRows.length })}</Badge>
              </div>
              <div className="mt-4 grid gap-3">
                <Select aria-label={t('review.batch.bucketLabel')} onValueChange={(value) => setTriageBucket(value as TriageBucket)} value={triageBucket}>
                  <option value="all">{t('review.batch.bucket.all')}</option>
                  <option value="blocked">{t('review.batch.bucket.blocked')}</option>
                  <option value="conflict">{t('review.batch.bucket.conflict')}</option>
                  <option value="needs_review">{t('review.batch.bucket.needsReview')}</option>
                  <option value="auto_safe">{t('review.batch.bucket.autoSafe')}</option>
                </Select>
                <Input
                  aria-label={t('review.batch.categoryLabel')}
                  onChange={(event) => setTriageCategory(event.target.value)}
                  placeholder={suggestedBatchCategory ? t('review.batch.suggestedPlaceholder', { value: suggestedBatchCategory }) : t('review.batch.categoryPlaceholder')}
                  value={triageCategory}
                />
                <div className="flex flex-wrap gap-2">
                  {suggestedBatchCategory ? (
                    <Button onClick={() => setTriageCategory(suggestedBatchCategory)} size="sm" type="button" variant="ghost">
                      {t('review.batch.useSuggested')}
                    </Button>
                  ) : null}
                  <Button disabled={!triageCategory.trim() || triageRows.length === 0 || triageApplying} onClick={() => void handleApplyBatchCategory()} size="sm" type="button">
                    {triageApplying ? t('review.batch.applying') : t('review.batch.applyCategory')}
                  </Button>
                  <Button disabled={triageRows.length === 0 || triageApplying} onClick={() => void handleApplyBatchIgnore(true)} size="sm" type="button" variant="secondary">
                    {t('review.batch.ignore')}
                  </Button>
                  <Button disabled={triageRows.length === 0 || triageApplying} onClick={() => void handleApplyBatchIgnore(false)} size="sm" type="button" variant="outline">
                    {t('review.batch.unignore')}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">{t('review.batch.footer')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {payload ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
          <CollectionPanel collections={payload.collections} onSelect={setSelectedCollectionId} rows={payload.rows} selectedCollectionId={selectedCollectionId || focusedCollectionId || ''} />
          <LearnedRulesPanel
            onAccept={(rule) => handleAcceptLearnedRule(rule)}
            onPromote={(rule) => {
              handlePromoteDraft(createRuleDraftFromLearnedSuggestion(rule), 'Loaded the learned suggestion into Rule Studio.', {
                source: 'learned-draft',
                title: 'Learned draft loaded',
                description:
                  'This draft was derived from a learned suggestion and is still review-only. It was not saved or applied automatically.',
                warnings: ['Preview the draft, then decide manually whether to save it or apply it to the overlay.'],
              })
            }}
          />
        </div>
      ) : null}
      {payload ? (
        <RuleStudioSheet
          jobId={jobId}
          onApplied={(nextPayload) => {
            setPayload(nextPayload)
          }}
          seedRule={seedRule}
          seedMeta={seedRuleMeta}
          seedRuleToken={seedRuleToken}
        />
      ) : null}

      {showEmptyState ? (
        <Card className="workspace-panel">
          <CardHeader>
            <CardTitle>{t('review.empty.title')}</CardTitle>
            <CardDescription>{t('review.empty.description')}</CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      {BUCKET_ORDER.map((bucket) => {
        const rows = rowsByBucket.get(bucket) ?? []
        if (rows.length === 0) {
          return null
        }
        return (
          <Card className="workspace-panel" key={bucket}>
            <CardHeader>
              <CardTitle className="capitalize">{bucket.replace('_', ' ')}</CardTitle>
              <CardDescription>{t('review.bucket.description', { count: rows.length })}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              {rows.map((row) => {
                const isExample = exampleRowIds.includes(row.id)
                return (
                  <div className="rounded-[1.2rem] border border-border/70 bg-muted/20 p-4" key={row.id}>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium tracking-[-0.015em] text-foreground">{row.file_name}</p>
                      <Badge variant={bucket === 'blocked' ? 'destructive' : bucket === 'conflict' ? 'warning' : bucket === 'auto_safe' ? 'success' : 'secondary'}>
                        {bucket}
                      </Badge>
                      {row.collection_title ? <Badge variant="outline">{row.collection_title}</Badge> : null}
                      <Button
                        disabled={!isExample && exampleRowIds.length >= 5}
                        onClick={() =>
                          setExampleRowIds((previous) =>
                            previous.includes(row.id) ? previous.filter((item) => item !== row.id) : [...previous, row.id],
                          )
                        }
                        size="sm"
                        type="button"
                        variant={isExample ? 'secondary' : 'outline'}
                      >
                        {isExample ? t('review.bucket.removeExample') : t('review.bucket.useExample')}
                      </Button>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">{row.title}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge variant="outline">{t('review.bucket.category', { value: row.category })}</Badge>
                      <Badge variant="outline">{t('review.bucket.confidence', { value: Math.round(row.confidence * 100) })}</Badge>
                      {row.error_code ? <Badge variant="warning">{t('review.bucket.error', { value: row.error_code })}</Badge> : null}
                      {row.learned_suggestions?.length ? <Badge variant="secondary">{t('review.bucket.learned', { count: row.learned_suggestions.length })}</Badge> : null}
                    </div>
                    {row.learned_suggestions?.length ? (
                      <div className="mt-3 rounded-[1rem] border border-dashed border-border/80 bg-card/60 p-3">
                        <p className="workspace-kicker">{t('review.bucket.whySurfacing')}</p>
                        <div className="mt-2 grid gap-2">
                          {row.learned_suggestions.map((suggestion) => (
                            <div className="grid gap-1" key={`${row.id}:${suggestion.signal_key}:${suggestion.suggestion_value}`}>
                              <p className="text-sm text-muted-foreground">{explainLearnedSuggestion(suggestion)}</p>
                              <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                                <span>confidence_label={suggestion.confidence_label ?? 'unspecified'}</span>
                                {suggestion.reuse_scope ? <span>reuse_scope={suggestion.reuse_scope}</span> : null}
                                {suggestion.source ? <span>source={suggestion.source}</span> : null}
                              </div>
                              {suggestion.explanation ? <p className="text-xs text-muted-foreground">{t('review.bucket.explanation', { value: suggestion.explanation })}</p> : null}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                )
              })}
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
