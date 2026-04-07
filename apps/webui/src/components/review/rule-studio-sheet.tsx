import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { applyReviewRule, createReviewRule, deleteReviewRule, listReviewRules, previewReviewRule, type ReviewQueuePayload } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import type { ReviewRule } from '@/lib/types'

export type RuleStudioDraft = Omit<ReviewRule, 'id'> & {
  id?: string
  draft_source?: string
  warnings?: string[]
  example_row_ids?: string[]
  explainability?: {
    selected_count: number
    selected_row_ids: string[]
    shared_media_types: string[]
    shared_review_buckets: string[]
    shared_query: string
    inferred_actions: string[]
    save_allowed: boolean
    apply_allowed: boolean
  }
}
export interface RuleStudioSeedMeta {
  source: 'example-draft' | 'learned-draft'
  title: string
  description: string
  warnings: string[]
}

function createDraft(): RuleStudioDraft {
  return {
    name: 'New rule',
    scope: 'manifest',
    description: '',
    version: 1,
    conditions: {
      query: '',
      statuses: [],
      media_types: [],
      categories: [],
      review_buckets: [],
    },
    actions: {},
  }
}

export function RuleStudioSheet({
  jobId,
  onApplied,
  seedRule,
  seedMeta,
  seedRuleToken = 0,
}: {
  jobId: string
  onApplied: (payload: ReviewQueuePayload) => void
  seedRule?: RuleStudioDraft | null
  seedMeta?: RuleStudioSeedMeta | null
  seedRuleToken?: number
}) {
  const { t } = useI18n()
  const [draft, setDraft] = useState<RuleStudioDraft>(createDraft())
  const [savedRules, setSavedRules] = useState<ReviewRule[]>([])
  const [previewCount, setPreviewCount] = useState<number | null>(null)
  const [activeSeedMeta, setActiveSeedMeta] = useState<RuleStudioSeedMeta | null>(seedMeta ?? null)
  const [saving, setSaving] = useState(false)
  const [applying, setApplying] = useState(false)
  const [deletingId, setDeletingId] = useState('')

  const refreshRules = useCallback(async () => {
    try {
      setSavedRules(await listReviewRules())
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('review.ruleStudio.loadFailed'))
    }
  }, [t])

  useEffect(() => {
    void refreshRules()
  }, [refreshRules])

  useEffect(() => {
    if (!seedRule) {
      return
    }
    setDraft(seedRule)
    setPreviewCount(null)
    setActiveSeedMeta(seedMeta ?? null)
    toast.success(seedMeta?.title ?? t('review.ruleStudio.loadedDraft'))
  }, [seedMeta, seedRule, seedRuleToken, t])

  async function handlePreview() {
    try {
      const preview = await previewReviewRule(jobId, undefined, draft)
      setPreviewCount(preview.matched_count)
      toast.success(t('review.ruleStudio.previewSuccess', { count: preview.matched_count }))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('review.ruleStudio.previewFailed'))
    }
  }

  async function handleSave() {
    setSaving(true)
    try {
      const created = await createReviewRule(draft)
      setDraft({
        id: created.id,
        ...draft,
        name: created.name,
        description: created.description ?? '',
        version: created.version,
        conditions: created.conditions,
        actions: created.actions,
      })
      await refreshRules()
      toast.success(t('review.ruleStudio.saveSuccess'))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('review.ruleStudio.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  async function handleApply() {
    setApplying(true)
    try {
      const payload = await applyReviewRule(jobId, undefined, draft)
      onApplied(payload)
      toast.success(
        t('review.ruleStudio.applySuccess', {
          count: payload.summary.needs_review + payload.summary.auto_safe + payload.summary.conflict + payload.summary.blocked,
        }),
      )
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('review.ruleStudio.applyFailed'))
    } finally {
      setApplying(false)
    }
  }

  async function handleApplySavedRule(rule: ReviewRule) {
    setApplying(true)
    try {
      const payload = await applyReviewRule(jobId, rule.id)
      onApplied(payload)
      toast.success(t('review.ruleStudio.applySavedSuccess', { name: rule.name }))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('review.ruleStudio.applyFailed'))
    } finally {
      setApplying(false)
    }
  }

  async function handleDeleteRule(rule: ReviewRule) {
    setDeletingId(rule.id)
    try {
      await deleteReviewRule(rule.id)
      await refreshRules()
      if (draft.id === rule.id) {
        setDraft(createDraft())
        setPreviewCount(null)
      }
      toast.success(t('review.ruleStudio.deleteSuccess', { name: rule.name }))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('review.ruleStudio.deleteFailed'))
    } finally {
      setDeletingId('')
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
      <Card>
        <CardHeader>
          <CardTitle>{t('review.ruleStudio.title')}</CardTitle>
          <CardDescription>{t('review.ruleStudio.description')}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              {draft.id ? t('review.ruleStudio.editingSaved', { name: draft.name }) : t('review.ruleStudio.editingInline')}
            </p>
            <Button
              onClick={() => {
                setDraft(createDraft())
                setPreviewCount(null)
                setActiveSeedMeta(null)
              }}
              size="sm"
              type="button"
              variant="ghost"
            >
              {t('review.ruleStudio.resetDraft')}
            </Button>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <Input aria-label={t('review.ruleStudio.ruleName')} onChange={(event) => setDraft((prev) => ({ ...prev, name: event.target.value }))} placeholder={t('review.ruleStudio.ruleName')} value={draft.name} />
            <Input
              aria-label={t('review.ruleStudio.queryCondition')}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  conditions: { ...prev.conditions, query: event.target.value },
                }))
              }
              placeholder={t('review.ruleStudio.queryPlaceholder')}
              value={draft.conditions.query ?? ''}
            />
            <Input
              aria-label={t('review.ruleStudio.setCategory')}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  actions: { ...prev.actions, set_category: event.target.value || undefined },
                }))
              }
              placeholder={t('review.ruleStudio.setCategory')}
              value={draft.actions.set_category ?? ''}
            />
            <Input
              aria-label={t('review.ruleStudio.targetPattern')}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  actions: { ...prev.actions, target_pattern: event.target.value || undefined },
                }))
              }
              placeholder={t('review.ruleStudio.targetPatternPlaceholder')}
              value={draft.actions.target_pattern ?? ''}
            />
          </div>
          {activeSeedMeta ? (
            <Alert>
              <AlertTitle>{activeSeedMeta.title}</AlertTitle>
              <AlertDescription className="space-y-2">
                <span className="block">{activeSeedMeta.description}</span>
                {activeSeedMeta.warnings.length > 0 ? (
                  <span className="block space-y-1">
                    {activeSeedMeta.warnings.map((warning) => (
                      <span className="block text-sm" key={warning}>
                        {warning}
                      </span>
                    ))}
                  </span>
                ) : null}
              </AlertDescription>
            </Alert>
          ) : null}
          <label className="flex items-center gap-3 text-sm">
            <Switch
              checked={Boolean(draft.actions.set_ignore)}
              onCheckedChange={(checked) =>
                setDraft((prev) => ({
                  ...prev,
                  actions: { ...prev.actions, set_ignore: checked },
                }))
              }
            />
            {t('review.ruleStudio.markIgnored')}
          </label>
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={() => void handlePreview()} type="button" variant="outline">
              {t('review.ruleStudio.preview')}
            </Button>
            <Button disabled={saving} onClick={() => void handleSave()} type="button" variant="secondary">
              {saving ? `${t('review.examples.drafting')}` : draft.id ? t('review.ruleStudio.update') : t('review.ruleStudio.save')}
            </Button>
            <Button disabled={applying} onClick={() => void handleApply()} type="button">
              {applying ? t('review.batch.applying') : t('review.ruleStudio.apply')}
            </Button>
            {previewCount !== null ? <p className="text-sm text-muted-foreground">{t('review.ruleStudio.matchedRows', { count: previewCount })}</p> : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('review.ruleStudio.savedTitle')}</CardTitle>
          <CardDescription>{t('review.ruleStudio.savedDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          {savedRules.length === 0 ? (
            <p className="rounded-xl border border-border p-4 text-sm text-muted-foreground">{t('review.ruleStudio.savedEmpty')}</p>
          ) : (
            savedRules.map((rule) => (
              <div className="rounded-xl border border-border p-3" key={rule.id}>
                <p className="font-medium">{rule.name}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {rule.description || t('review.ruleStudio.noDescription')} | {t('review.ruleStudio.scopeVersion', { scope: rule.scope, version: rule.version })}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    onClick={() => {
                      setDraft({ ...rule })
                      setActiveSeedMeta(null)
                    }}
                    size="sm"
                    type="button"
                    variant="outline"
                  >
                    {t('review.ruleStudio.loadEditor')}
                  </Button>
                  <Button disabled={applying} onClick={() => void handleApplySavedRule(rule)} size="sm" type="button" variant="secondary">
                    {t('review.ruleStudio.applySaved')}
                  </Button>
                  <Button disabled={deletingId === rule.id} onClick={() => void handleDeleteRule(rule)} size="sm" type="button" variant="ghost">
                    {deletingId === rule.id ? t('review.ruleStudio.deleting') : t('review.ruleStudio.delete')}
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}
