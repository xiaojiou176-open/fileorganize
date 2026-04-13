import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { listLearnedRules, resetLearnedRules } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import type { LearnedRule } from '@/lib/types'
import { explainLearnedSuggestion } from './review-intelligence'

export function LearnedRulesPanel({
  onAccept,
  onPromote,
}: {
  onAccept?: (rule: LearnedRule) => Promise<void> | void
  onPromote?: (rule: LearnedRule) => void
} = {}) {
  const { t } = useI18n()
  const [rules, setRules] = useState<LearnedRule[]>([])
  const [acceptingId, setAcceptingId] = useState('')
  const [dismissedRuleIds, setDismissedRuleIds] = useState<string[]>([])

  const refresh = useCallback(async () => {
    try {
      setRules(await listLearnedRules())
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('review.learned.loadFailed'))
    }
  }, [t])

  useEffect(() => {
    void refresh()
  }, [refresh])

  async function handleReset() {
    try {
      await resetLearnedRules()
      setRules([])
      toast.success(t('review.learned.resetSuccess'))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('review.learned.resetFailed'))
    }
  }

  const visibleRules = useMemo(() => rules.filter((rule) => !dismissedRuleIds.includes(rule.id)), [dismissedRuleIds, rules])

  return (
    <Card className="workspace-panel">
      <CardHeader>
        <CardTitle>{t('review.learned.title')}</CardTitle>
        <CardDescription>{t('review.learned.description')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex justify-end">
          <Button onClick={() => void handleReset()} size="sm" variant="outline">
            {t('review.learned.reset')}
          </Button>
        </div>
        {visibleRules.length === 0 ? (
          <p className="rounded-xl border border-border p-4 text-sm text-muted-foreground">{t('review.learned.empty')}</p>
        ) : (
          <div className="grid gap-3">
            {visibleRules.map((rule) => (
              <div className="rounded-[1.2rem] border border-border/70 bg-muted/20 p-4" key={rule.id}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="font-medium tracking-[-0.015em] text-foreground">
                    {rule.suggestion_type}: {rule.suggestion_value}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <span className="inline-flex items-center rounded-full border border-transparent bg-secondary px-2.5 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-secondary-foreground">
                      {Math.round(rule.confidence * 100)}%
                    </span>
                    <span className="inline-flex items-center rounded-full border border-border/90 bg-transparent px-2.5 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                      count {rule.count}
                    </span>
                  </div>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  signal={rule.signal_key}:{rule.signal_value} | confidence={Math.round(rule.confidence * 100)}%
                  {rule.confidence_label ? ` (${rule.confidence_label})` : ''} | count={rule.count}
                </p>
                {rule.source || rule.explanation ? (
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                    {rule.source ? (
                      <span className="inline-flex items-center rounded-full border border-border/90 bg-transparent px-2.5 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                        source={rule.source}
                      </span>
                    ) : null}
                    {rule.reuse_scope ? (
                      <span className="inline-flex items-center rounded-full border border-border/90 bg-transparent px-2.5 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                        reuse_scope={rule.reuse_scope}
                      </span>
                    ) : null}
                  </div>
                ) : null}
                <p className="mt-2 text-sm text-muted-foreground">{explainLearnedSuggestion(rule)}</p>
                {rule.explanation ? <p className="mt-2 text-xs leading-5 text-muted-foreground">explanation={rule.explanation}</p> : null}
                <div className="mt-3 flex flex-wrap gap-2">
                  {onAccept ? (
                    <Button
                      disabled={acceptingId === rule.id}
                      onClick={async () => {
                        setAcceptingId(rule.id)
                        try {
                          await onAccept(rule)
                        } finally {
                          setAcceptingId('')
                        }
                      }}
                      size="sm"
                      type="button"
                    >
                      {acceptingId === rule.id ? t('review.learned.accepting') : t('review.learned.accept')}
                    </Button>
                  ) : null}
                  {onPromote ? (
                    <Button onClick={() => onPromote(rule)} size="sm" type="button" variant="secondary">
                      {t('review.learned.promote')}
                    </Button>
                  ) : null}
                  <Button
                    onClick={() => setDismissedRuleIds((prev) => [...prev, rule.id])}
                    size="sm"
                    type="button"
                    variant="ghost"
                  >
                    {t('review.learned.ignore')}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
