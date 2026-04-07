import type { ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/lib/i18n'
import { cn } from '@/lib/utils'

interface DataTableToolbarProps {
  leading?: ReactNode
  trailing?: ReactNode
  selectionCount?: number
  totalCount?: number
  onClearSelection?: () => void
  className?: string
}

export function DataTableToolbar({
  leading,
  trailing,
  selectionCount = 0,
  totalCount,
  onClearSelection,
  className,
}: DataTableToolbarProps) {
  const { t } = useI18n()
  return (
    <div className={cn('grid gap-3 rounded-xl border border-border p-3 md:grid-cols-[1fr_auto]', className)}>
      <div className="flex flex-wrap items-center gap-2">
        {leading}
        {typeof totalCount === 'number' ? <Badge variant="outline">{t('dataTable.toolbar.visibleCount', { count: totalCount })}</Badge> : null}
        <Badge variant="outline">{t('dataTable.toolbar.selectedCount', { count: selectionCount })}</Badge>
        {selectionCount > 0 && onClearSelection ? (
          <Button onClick={onClearSelection} size="sm" variant="ghost">
            {t('dataTable.toolbar.clearSelection')}
          </Button>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center justify-start gap-2 md:justify-end">{trailing}</div>
    </div>
  )
}
