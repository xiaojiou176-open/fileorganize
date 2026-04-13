import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useI18n } from '@/lib/i18n'
import type { CollectionSummary, ManifestRow } from '@/lib/types'

function summarizeCollection(rows: ManifestRow[], t: ReturnType<typeof useI18n>['t']) {
  const bucketCounts = {
    blocked: 0,
    conflict: 0,
    needs_review: 0,
    auto_safe: 0,
  }
  let learnedRows = 0
  for (const row of rows) {
    const bucket = row.review_bucket ?? 'needs_review'
    bucketCounts[bucket] += 1
    if ((row.learned_suggestions?.length ?? 0) > 0) {
      learnedRows += 1
    }
  }
  const nextStep =
    bucketCounts.blocked > 0
      ? t('review.collections.nextStep.blocked')
      : bucketCounts.conflict > 0
        ? t('review.collections.nextStep.conflict')
        : bucketCounts.needs_review > 0
          ? t('review.collections.nextStep.review')
          : t('review.collections.nextStep.ready')

  return { bucketCounts, learnedRows, nextStep }
}

export function CollectionPanel({
  collections,
  rows,
  selectedCollectionId,
  onSelect,
}: {
  collections: CollectionSummary[]
  rows: ManifestRow[]
  selectedCollectionId?: string
  onSelect?: (collectionId: string) => void
}) {
  const { t } = useI18n()
  return (
    <Card className="workspace-panel">
      <CardHeader>
        <CardTitle>{t('review.collections.title')}</CardTitle>
        <CardDescription>{t('review.collections.description')}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-2">
        {collections.map((collection) => {
          const selected = selectedCollectionId === collection.id
          const collectionRows = rows.filter((row) => row.collection_id === collection.id)
          const summary = summarizeCollection(collectionRows, t)
          return (
            <Button
              className={`h-auto justify-start rounded-[1.2rem] border p-4 text-left transition-all ${
                selected
                  ? 'border-primary/15 bg-[linear-gradient(135deg,hsl(var(--accent))_0%,hsl(var(--card))_100%)] shadow-card'
                  : 'border-border/70 bg-card/85 hover:border-primary/10 hover:bg-muted/25'
              }`}
              key={collection.id}
              onClick={() => onSelect?.(collection.id)}
              type="button"
              variant="ghost"
            >
              <div className="flex w-full items-start justify-between gap-3">
                <div className="space-y-2">
                  <p className="font-medium tracking-[-0.015em] text-foreground">{collection.title}</p>
                  <p className="text-xs leading-5 text-muted-foreground">{collection.reason}</p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  <Badge variant={selected ? 'secondary' : 'outline'}>{t('review.collections.rows', { count: collection.row_ids.length })}</Badge>
                  <Badge variant="outline">{t('review.collections.confidence', { value: Math.round(collection.confidence * 100) })}</Badge>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                {collection.kind ? <Badge variant="outline">{t('review.collections.kind', { value: collection.kind })}</Badge> : null}
                {collection.batch_hint ? <Badge variant="outline">{t('review.collections.hint', { value: collection.batch_hint })}</Badge> : null}
                {collection.capture_day ? <Badge variant="outline">{t('review.collections.day', { value: collection.capture_day })}</Badge> : null}
                {collection.dominant_media_type ? <Badge variant="outline">{t('review.collections.media', { value: collection.dominant_media_type })}</Badge> : null}
              </div>
              {collection.explainability?.length ? (
                <p className="mt-2 text-xs text-muted-foreground">{t('review.collections.why', { value: collection.explainability.join(' · ') })}</p>
              ) : null}
              <p className="mt-2 text-xs text-muted-foreground">{summary.nextStep}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                {summary.bucketCounts.blocked > 0 ? <Badge variant="destructive">{t('review.collections.blocked', { count: summary.bucketCounts.blocked })}</Badge> : null}
                {summary.bucketCounts.conflict > 0 ? <Badge variant="warning">{t('review.collections.conflict', { count: summary.bucketCounts.conflict })}</Badge> : null}
                {summary.bucketCounts.needs_review > 0 ? <Badge variant="secondary">{t('review.collections.needsReview', { count: summary.bucketCounts.needs_review })}</Badge> : null}
                {summary.bucketCounts.auto_safe > 0 ? <Badge variant="success">{t('review.collections.autoSafe', { count: summary.bucketCounts.auto_safe })}</Badge> : null}
                {summary.learnedRows > 0 ? <Badge variant="outline">{t('review.collections.learningCues', { count: summary.learnedRows })}</Badge> : null}
              </div>
            </Button>
          )
        })}
        {collections.length === 0 ? <p className="rounded-xl border border-border p-4 text-sm text-muted-foreground">{t('review.collections.empty')}</p> : null}
      </CardContent>
    </Card>
  )
}
