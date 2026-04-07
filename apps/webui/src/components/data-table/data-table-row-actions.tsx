import { cn } from '@/lib/utils'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useI18n } from '@/lib/i18n'

export interface DataTableRowActionItem {
  key: string
  label: string
  onSelect: () => void
  disabled?: boolean
  destructive?: boolean
}

interface DataTableRowActionsProps {
  items: DataTableRowActionItem[]
  label?: string
  className?: string
}

export function DataTableRowActions({ items, label, className }: DataTableRowActionsProps) {
  const { t } = useI18n()
  if (items.length === 0) {
    return null
  }

  const resolvedLabel = label ?? t('dataTable.rowActions.label')

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          'inline-flex list-none cursor-pointer rounded-lg border border-border px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground',
          className,
        )}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => event.stopPropagation()}
      >
        {resolvedLabel}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" onClick={(event) => event.stopPropagation()}>
        {items.map((item) => (
          <DropdownMenuItem
            destructive={item.destructive}
            disabled={item.disabled}
            key={item.key}
            onSelect={(event) => {
              event.preventDefault()
              item.onSelect()
            }}
          >
            {item.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
