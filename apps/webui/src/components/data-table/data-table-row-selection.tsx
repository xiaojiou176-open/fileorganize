import type { Row, Table as TanStackTable } from '@tanstack/react-table'

import { Checkbox } from '@/components/ui/checkbox'
import { useI18n } from '@/lib/i18n'
import { cn } from '@/lib/utils'

interface DataTableRowSelectionHeaderProps<TData> {
  table: TanStackTable<TData>
  ariaLabel?: string
  className?: string
  usePageRows?: boolean
}

interface DataTableRowSelectionCellProps<TData> {
  row: Row<TData>
  ariaLabel?: string
  className?: string
}

export function DataTableRowSelectionHeader<TData>({
  table,
  ariaLabel,
  className,
  usePageRows = true,
}: DataTableRowSelectionHeaderProps<TData>) {
  const { t } = useI18n()
  const checked = usePageRows ? table.getIsAllPageRowsSelected() : table.getIsAllRowsSelected()
  const indeterminate = usePageRows
    ? table.getIsSomePageRowsSelected() && !table.getIsAllPageRowsSelected()
    : table.getIsSomeRowsSelected() && !table.getIsAllRowsSelected()
  const resolvedAriaLabel = ariaLabel ?? t('dataTable.rowSelection.selectAll')

  return (
    <Checkbox
      aria-label={resolvedAriaLabel}
      checked={indeterminate ? 'indeterminate' : checked}
      className={cn(className)}
      onCheckedChange={(nextChecked) => {
        if (usePageRows) {
          table.toggleAllPageRowsSelected(nextChecked)
          return
        }
        table.toggleAllRowsSelected(nextChecked)
      }}
      onClick={(event) => event.stopPropagation()}
    />
  )
}

export function DataTableRowSelectionCell<TData>({ row, ariaLabel, className }: DataTableRowSelectionCellProps<TData>) {
  const { t } = useI18n()
  const resolvedAriaLabel = ariaLabel ?? t('dataTable.rowSelection.selectRow')
  return (
    <Checkbox
      aria-label={resolvedAriaLabel}
      checked={row.getIsSelected()}
      className={cn(className)}
      onCheckedChange={(nextChecked) => row.toggleSelected(nextChecked)}
      onClick={(event) => event.stopPropagation()}
    />
  )
}
