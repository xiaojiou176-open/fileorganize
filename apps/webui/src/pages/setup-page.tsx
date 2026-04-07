import { CheckCircle2, FolderOpen, KeyRound, Sparkles, Wand2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { getRuntimeSettings, listStrategyPacks, updateRuntimeSettings, validateRuntimeSettings, type RuntimeSettings } from '@/lib/api'
import type { StrategyPack } from '@/lib/types'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { useI18n } from '@/lib/i18n'
import { createRouteIntentPrefetchHandlers } from '@/routes/lazy-routes'

const MODEL_OPTIONS = ['gemini-3-flash-preview', 'gemini-3.1-pro-preview']

type SetupFormState = {
  apiKey: string
  activeStrategyPackId: string
  model: string
  inputRoot: string
  outputRoot: string
  workers: string
  categories: string
  maxFiles: string
  maxTotalMb: string
  maxFileMb: string
}

export function SetupPage() {
  const { t } = useI18n()
  const [settings, setSettings] = useState<RuntimeSettings | null>(null)
  const [strategyPacks, setStrategyPacks] = useState<StrategyPack[]>([])
  const [form, setForm] = useState<SetupFormState>({
    apiKey: '',
    activeStrategyPackId: '',
    model: 'gemini-3-flash-preview',
    inputRoot: '~/.movi-organizer/workspaces/default/data/raw',
    outputRoot: '~/.movi-organizer/workspaces/default/data/organized',
    workers: '1',
    categories: 'work,travel,docs,product,other',
    maxFiles: '500',
    maxTotalMb: '4096',
    maxFileMb: '128',
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [checking, setChecking] = useState(false)
  const analyzePrefetch = createRouteIntentPrefetchHandlers('analyze')
  const dashboardPrefetch = createRouteIntentPrefetchHandlers('dashboard')
  const selectedPack = useMemo(
    () => strategyPacks.find((pack) => pack.id === form.activeStrategyPackId) ?? null,
    [form.activeStrategyPackId, strategyPacks],
  )

  const summarizeApiStatus = (next: RuntimeSettings | null): string => {
    if (!next) {
      return t('setup.apiStatus.loading')
    }
    if (next.api_key_status === 'configured') { // pragma: allowlist secret
      return t('setup.apiStatus.connected')
    }
    if (next.api_key_status === 'placeholder') { // pragma: allowlist secret
      return t('setup.apiStatus.placeholder')
    }
    return t('setup.apiStatus.missing')
  }

  useEffect(() => {
    let alive = true
    void (async () => {
      try {
        const [next, packs] = await Promise.all([getRuntimeSettings(), listStrategyPacks()])
        if (!alive) {
          return
        }
        setSettings(next)
        setStrategyPacks(packs.items)
        setForm((prev) => ({
          apiKey: '',
          activeStrategyPackId: next.active_strategy_pack_id || packs.active_strategy_pack_id || prev.activeStrategyPackId,
          model: next.model || prev.model,
          inputRoot: next.input_root || prev.inputRoot,
          outputRoot: next.output_root || prev.outputRoot,
          workers: String(next.analyze_defaults.workers || prev.workers),
          categories: next.analyze_defaults.categories.join(',') || prev.categories,
          maxFiles: String(next.analyze_defaults.max_files || prev.maxFiles),
          maxTotalMb: String(next.analyze_defaults.max_total_mb || prev.maxTotalMb),
          maxFileMb: String(next.analyze_defaults.max_file_mb || prev.maxFileMb),
        }))
      } catch (error) {
        if (alive) {
          toast.error(error instanceof Error ? error.message : 'Failed to load the first-run setup page.')
        }
      } finally {
        if (alive) {
          setLoading(false)
        }
      }
    })()
    return () => {
      alive = false
    }
  }, [])

  const stage = useMemo(() => {
    if (!settings) {
      return 'loading'
    }
    if (settings.ready) {
      return 'ready'
    }
    if (settings.has_api_key || settings.input_root_exists || settings.output_root_exists) {
      return 'configured'
    }
    return 'not_configured'
  }, [settings])

  async function handleSave() {
    setSaving(true)
    try {
      const next = await updateRuntimeSettings({
        apiKey: form.apiKey.trim().length > 0 ? form.apiKey.trim() : undefined,
        activeStrategyPackId: form.activeStrategyPackId,
        model: form.model,
        inputRoot: form.inputRoot,
        outputRoot: form.outputRoot,
        workers: Number(form.workers),
        categories: form.categories,
        maxFiles: Number(form.maxFiles),
        maxTotalMb: Number(form.maxTotalMb),
        maxFileMb: Number(form.maxFileMb),
        createMissingDirs: true,
      })
      setSettings(next)
      setForm((prev) => ({ ...prev, apiKey: '' }))
      toast.success(next.ready ? 'Initial setup is complete. You can start organizing files now.' : 'Settings were saved. Finish the remaining items to continue.')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save runtime settings.')
    } finally {
      setSaving(false)
    }
  }

  async function handleValidate() {
    setChecking(true)
    try {
      const next = await validateRuntimeSettings()
      setSettings(next)
      toast.success(next.ready ? 'Connection checks passed. You can start organizing files now.' : 'Validation finished, but some items still need attention.')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Connection check failed.')
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-3xl border border-border/70 bg-[linear-gradient(135deg,hsl(var(--brand-soft))_0%,hsl(var(--card))_58%,hsl(var(--accent)/0.55)_100%)] p-6 shadow-card sm:p-8">
        <div className="pointer-events-none absolute -right-16 -top-12 h-52 w-52 rounded-full bg-primary/10 blur-3xl" />
        <div className="max-w-3xl space-y-4">
          <Badge variant={stage === 'ready' ? 'success' : 'secondary'}>
            {stage === 'ready'
              ? t('setup.badge.ready')
              : stage === 'configured'
                ? t('setup.badge.oneStepLeft')
                : loading
                  ? t('setup.badge.loading')
                  : t('setup.badge.firstRun')}
          </Badge>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t('setup.hero.title')}</h1>
          <p className="text-sm text-muted-foreground sm:text-base">{t('setup.hero.description')}</p>
          <div className="flex flex-wrap gap-3">
            <Button disabled={saving || checking} onClick={() => void handleSave()}>
              <Wand2 className="mr-2 h-4 w-4" />
              {saving ? t('setup.cta.saving') : t('setup.cta.save')}
            </Button>
            <Button disabled={checking} onClick={() => void handleValidate()} variant="outline">
              <Sparkles className="mr-2 h-4 w-4" />
              {checking ? t('setup.cta.checking') : t('setup.cta.check')}
            </Button>
            <Button asChild variant="secondary">
              <Link {...dashboardPrefetch} to="/">
                {t('setup.cta.backHome')}
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {settings && settings.warnings.length > 0 ? (
        <Alert className="border-warning/30 bg-warning/10">
          <AlertTitle>{t('setup.alert.incomplete.title')}</AlertTitle>
          <AlertDescription>{t('setup.alert.incomplete.description', { warnings: settings.warnings.join('; ') })}</AlertDescription>
        </Alert>
      ) : null}

      {settings?.ready ? (
        <Alert className="border-success/30 bg-success/10">
          <AlertTitle className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            {t('setup.alert.ready.title')}
          </AlertTitle>
          <AlertDescription>{t('setup.alert.ready.description')}</AlertDescription>
        </Alert>
      ) : null}

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>{t('setup.card.connect.title')}</CardTitle>
            <CardDescription>{t('setup.card.connect.description')}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="setup-api-key">
                {t('setup.field.apiKey')}
              </label>
              <Input
                id="setup-api-key"
                onChange={(event) => setForm((prev) => ({ ...prev, apiKey: event.target.value }))}
                placeholder={settings?.has_api_key ? t('setup.field.apiKeyPlaceholderKeep') : t('setup.field.apiKeyPlaceholderPaste')}
                type="password"
                value={form.apiKey}
              />
              <p className="text-xs text-muted-foreground">{t('setup.field.apiKeyStatus', { status: summarizeApiStatus(settings) })}</p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="setup-pack">
                {t('setup.field.strategyPack')}
              </label>
              <Select
                id="setup-pack"
                onValueChange={(value) =>
                  setForm((prev) => {
                    const nextPack = strategyPacks.find((item) => item.id === value)
                    return {
                      ...prev,
                      activeStrategyPackId: value,
                      model: nextPack?.model || prev.model,
                      categories: nextPack?.categories.join(',') || prev.categories,
                      workers: nextPack ? String(nextPack.workers) : prev.workers,
                    }
                  })
                }
                value={form.activeStrategyPackId}
              >
                {strategyPacks.map((pack) => (
                  <option key={pack.id} value={pack.id}>
                    {pack.name}
                  </option>
                ))}
              </Select>
              <p className="text-xs text-muted-foreground">{t('setup.field.strategyPackHint')}</p>
              {selectedPack ? (
                <div className="rounded-xl border border-border bg-muted/30 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium">{selectedPack.name}</p>
                    <Badge variant="secondary">template only</Badge>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {selectedPack.description || 'Use this pack when the same kind of batch keeps showing up and you want Analyze to start from a familiar default recipe.'}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <Badge variant="outline">model: {selectedPack.model || 'keep current default'}</Badge>
                    <Badge variant="outline">workers: {selectedPack.workers}</Badge>
                    <Badge variant="outline">categories: {selectedPack.categories.join(', ') || 'none'}</Badge>
                    <Badge variant="outline">review threshold: {Math.round(selectedPack.review_confidence_threshold * 100)}%</Badge>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="setup-model">
                Default model
              </label>
              <Select id="setup-model" onValueChange={(value) => setForm((prev) => ({ ...prev, model: value }))} value={form.model}>
                {MODEL_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="setup-input-root">
                Default photo source folder
              </label>
              <Input
                id="setup-input-root"
                onChange={(event) => setForm((prev) => ({ ...prev, inputRoot: event.target.value }))}
                placeholder="For example: ~/Pictures/to-sort"
                value={form.inputRoot}
              />
              <p className="text-xs text-muted-foreground">Analyze can use this connected folder in one click, or you can still upload a one-off batch.</p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="setup-output-root">
                Default organized output folder
              </label>
              <Input
                id="setup-output-root"
                onChange={(event) => setForm((prev) => ({ ...prev, outputRoot: event.target.value }))}
                placeholder="For example: ~/Pictures/Movi Organized"
                value={form.outputRoot}
              />
              <p className="text-xs text-muted-foreground">Saving creates missing directories automatically so you do not have to build the folder tree by hand first.</p>
            </div>

            <div className="space-y-2 md:col-span-2">
              <label className="text-sm font-medium" htmlFor="setup-categories">
                Default category hint
              </label>
              <Input id="setup-categories" onChange={(event) => setForm((prev) => ({ ...prev, categories: event.target.value }))} value={form.categories} />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="setup-workers">
                Default parallel workers
              </label>
              <Input id="setup-workers" onChange={(event) => setForm((prev) => ({ ...prev, workers: event.target.value }))} value={form.workers} />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="setup-max-files">
                Default file-count limit
              </label>
              <Input id="setup-max-files" onChange={(event) => setForm((prev) => ({ ...prev, maxFiles: event.target.value }))} value={form.maxFiles} />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="setup-max-total-mb">
                Default total-size limit (MB)
              </label>
              <Input
                id="setup-max-total-mb"
                onChange={(event) => setForm((prev) => ({ ...prev, maxTotalMb: event.target.value }))}
                value={form.maxTotalMb}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="setup-max-file-mb">
                Default single-file limit (MB)
              </label>
              <Input id="setup-max-file-mb" onChange={(event) => setForm((prev) => ({ ...prev, maxFileMb: event.target.value }))} value={form.maxFileMb} />
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <StatusCard icon={KeyRound} label="AI connection" value={settings?.has_api_key ? 'API key saved' : 'API key not configured'} />
          <StatusCard
            icon={FolderOpen}
            label="Source folder"
            value={settings?.input_root_exists ? 'Ready to scan' : 'Created automatically when you save'}
          />
          <StatusCard
            icon={FolderOpen}
            label="Organized output"
            value={settings?.output_root_exists ? 'Ready to write' : 'Created automatically when you save'}
          />

          <Card>
            <CardHeader>
              <CardTitle>What to do next</CardTitle>
              <CardDescription>The smooth path should look like this:</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>1. Connect the API key and default folders here.</p>
              <p>2. Go to Analyze and use the connected folder or upload the current batch.</p>
              <p>3. Review the manifest in Review Queue, run a preview, then start the real apply.</p>
              <Button asChild className="w-full" disabled={!settings?.ready}>
                <Link {...analyzePrefetch} to="/analyze">
                  Continue to Analyze
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  )
}

function StatusCard({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof FolderOpen
  label: string
  value: string
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 pt-6">
        <div className="grid h-11 w-11 place-items-center rounded-2xl border border-border bg-muted/50">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="font-medium">{value}</p>
        </div>
      </CardContent>
    </Card>
  )
}
