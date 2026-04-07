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
    const timer = window.setTimeout(() => {
      void refresh()
    }, 0)
    return () => {
      window.clearTimeout(timer)
    }
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
    <Card>
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
              <div className="rounded-xl border border-border p-3" key={rule.id}>
                <p className="font-medium">{rule.suggestion_type}: {rule.suggestion_value}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  signal={rule.signal_key}:{rule.signal_value} | confidence={Math.round(rule.confidence * 100)}%
                  {rule.confidence_label ? ` (${rule.confidence_label})` : ''} | count={rule.count}
                </p>
                {rule.source || rule.explanation ? (
                  <div className="mt-2 grid gap-1 text-xs text-muted-foreground">
                    {rule.source ? <p>source={rule.source}</p> : null}
                    {rule.explanation ? <p>explanation={rule.explanation}</p> : null}
                    {rule.reuse_scope ? <p>reuse_scope={rule.reuse_scope}</p> : null}
                  </div>
                ) : null}
                <p className="mt-2 text-sm text-muted-foreground">{explainLearnedSuggestion(rule)}</p>
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
