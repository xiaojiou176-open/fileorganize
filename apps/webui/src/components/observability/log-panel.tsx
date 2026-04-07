import { Copy, RefreshCw } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Select } from '@/components/ui/select'
import { PanelSkeleton } from '@/components/ui/skeleton'
import { useI18n } from '@/lib/i18n'
import { cn, formatDate } from '@/lib/utils'
import type { JobEvent } from '@/lib/types'

interface LogPanelProps {
  title?: string
  description?: string
  events: JobEvent[]
  connectionState?: 'connecting' | 'open' | 'error' | 'unsupported' | 'closed'
  onRefresh?: () => void
  className?: string
}

function normalizeLevel(level: string): 'debug' | 'info' | 'warn' | 'error' {
  const normalized = level.trim().toLowerCase()
  if (normalized.includes('error') || normalized.includes('fatal')) {
    return 'error'
  }
  if (normalized.includes('warn')) {
    return 'warn'
  }
  if (normalized.includes('debug') || normalized.includes('trace')) {
    return 'debug'
  }
  return 'info'
}

function formatFields(fields?: Record<string, unknown>): string {
  if (!fields) {
    return ''
  }
  return Object.entries(fields)
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(' ')
}

export function LogPanel({
  title = 'Runtime Logs',
  description = 'Filter by level, auto-scroll, and copy log output.',
  events,
  connectionState = 'unsupported',
  onRefresh,
  className,
}: LogPanelProps) {
  const { t, locale } = useI18n()
  const [level, setLevel] = useState<'all' | 'debug' | 'info' | 'warn' | 'error'>('all')
  const [autoScroll, setAutoScroll] = useState(true)
  const viewportRef = useRef<HTMLDivElement | null>(null)

  const filtered = useMemo(() => {
    return events.filter((event) => {
      const normalized = normalizeLevel(event.level)
      return level === 'all' || normalized === level
    })
  }, [events, level])
  const levelCount = useMemo(() => {
    return {
      total: events.length,
      error: events.filter((event) => normalizeLevel(event.level) === 'error').length,
      warn: events.filter((event) => normalizeLevel(event.level) === 'warn').length,
    }
  }, [events])

  useEffect(() => {
    if (!autoScroll || !viewportRef.current) {
      return
    }
    viewportRef.current.scrollTop = viewportRef.current.scrollHeight
  }, [autoScroll, filtered])

  const copyLogs = async () => {
    const text = filtered
      .map((event) => {
        const normalized = normalizeLevel(event.level).toUpperCase()
        const fields = formatFields(event.fields)
        return `[${formatDate(event.timestamp, locale)}] [${normalized}] ${event.message}${fields ? ` ${fields}` : ''}`
      })
      .join('\n')

    if (text.length === 0) {
      toast.message(t('logs.copyNoMatch'))
      return
    }

    try {
      await navigator.clipboard.writeText(text)
      toast.success(t('logs.copySuccess'))
    } catch {
      toast.error(t('logs.copyError'))
    }
  }

  const stateBadge =
    connectionState === 'open'
      ? { label: t('logs.sseConnected'), variant: 'success' as const, pulse: true }
      : connectionState === 'connecting'
        ? { label: t('logs.sseConnecting'), variant: 'secondary' as const, pulse: true }
        : connectionState === 'error'
          ? { label: t('logs.sseFailed'), variant: 'destructive' as const, pulse: false }
          : connectionState === 'unsupported'
            ? { label: t('logs.sseUnavailable'), variant: 'warning' as const, pulse: false }
            : { label: t('logs.sseClosed'), variant: 'outline' as const, pulse: false }

  return (
    <Card className={cn('motion-surface', className)}>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center justify-between gap-2">
          <span>{title}</span>
          <Badge className={stateBadge.pulse ? 'motion-status-pulse' : ''} variant={stateBadge.variant}>
            {stateBadge.label}
          </Badge>
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Select onValueChange={(value) => setLevel(value as 'all' | 'debug' | 'info' | 'warn' | 'error')} value={level}>
            <option value="all">{t('logs.allLevels')}</option>
            <option value="debug">DEBUG</option>
            <option value="info">INFO</option>
            <option value="warn">WARN</option>
            <option value="error">ERROR</option>
          </Select>
          <label className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs text-muted-foreground">
            <Checkbox checked={autoScroll} onCheckedChange={setAutoScroll} />
            {t('logs.autoScroll')}
          </label>
          <Button onClick={copyLogs} size="sm" variant="outline">
            <Copy className="mr-1.5 h-3.5 w-3.5" />
            {t('logs.copy')}
          </Button>
          {onRefresh ? (
            <Button onClick={onRefresh} size="sm" variant="ghost">
              <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
              {t('common.refresh')}
            </Button>
          ) : null}
          <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
            <span>{t('logs.totalCount', { count: levelCount.total })}</span>
            <span>{t('logs.warnCount', { count: levelCount.warn })}</span>
            <span>{t('logs.errorCount', { count: levelCount.error })}</span>
          </div>
        </div>

        <div className="max-h-[300px] overflow-auto rounded-xl border border-border bg-muted/20 p-2" ref={viewportRef}>
          {filtered.length === 0 && connectionState === 'connecting' ? (
            <PanelSkeleton className="border-none bg-transparent p-1" lines={4} />
          ) : null}
          {filtered.length === 0 && connectionState !== 'connecting' ? <p className="p-2 text-xs text-muted-foreground">{t('logs.empty')}</p> : null}
          <div className="space-y-1 font-mono text-xs">
            {filtered.map((event, index) => {
              const normalized = normalizeLevel(event.level)
              const fields = formatFields(event.fields)
              return (
                <div
                  className={cn(
                    'motion-log-row rounded-md px-2 py-1',
                    normalized === 'error'
                      ? 'bg-destructive/10 text-destructive'
                      : normalized === 'warn'
                        ? 'bg-warning/15 text-warning-ink'
                        : normalized === 'debug'
                          ? 'bg-muted text-muted-foreground'
                          : 'text-foreground',
                  )}
                  key={`${event.timestamp}-${event.message}-${index}`}
                >
                  <span className="mr-2 text-muted-foreground">{formatDate(event.timestamp, locale)}</span>
                  <span className="mr-2">[{normalized.toUpperCase()}]</span>
                  <span>{event.message}</span>
                  {fields ? <span className="ml-2 text-muted-foreground">{fields}</span> : null}
                </div>
              )
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
