import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useI18n } from '@/lib/i18n'
import type { ReviewQueueSummary as ReviewQueueSummaryType } from '@/lib/types'

export function ReviewQueueSummary({ summary }: { summary: ReviewQueueSummaryType }) {
  const { t } = useI18n()
  const cards = [
    { label: t('review.summary.autoSafe'), value: summary.auto_safe, tone: 'success' },
    { label: t('review.summary.needsReview'), value: summary.needs_review, tone: 'secondary' },
    { label: t('review.summary.conflicts'), value: summary.conflict, tone: 'warning' },
    { label: t('review.summary.blocked'), value: summary.blocked, tone: 'destructive' },
  ] as const

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('review.summary.title')}</CardTitle>
        <CardDescription>{t('review.summary.description')}</CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-4">
        {cards.map((card) => (
          <div className="rounded-xl border border-border p-3" key={card.label}>
            <p className="text-xs text-muted-foreground">{card.label}</p>
            <p className="text-2xl font-semibold">{card.value}</p>
            <div className="mt-2">
              <Badge variant={card.tone === 'success' ? 'success' : card.tone === 'warning' ? 'warning' : card.tone === 'destructive' ? 'destructive' : 'secondary'}>
                {t('review.summary.ofTotal', { count: summary.total })}
              </Badge>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
