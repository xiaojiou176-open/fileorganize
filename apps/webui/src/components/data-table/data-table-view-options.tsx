import type { Table as TanStackTable } from '@tanstack/react-table'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useI18n } from '@/lib/i18n'

interface DataTableViewOptionsProps<TData> {
  table: TanStackTable<TData>
  label?: string
}

export function DataTableViewOptions<TData>({ table, label }: DataTableViewOptionsProps<TData>) {
  const { t } = useI18n()
  const columns = table
    .getAllLeafColumns()
    .filter((column) => column.getCanHide())

  if (columns.length === 0) {
    return null
  }

  const resolvedLabel = label ?? t('dataTable.viewOptions.label')

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button className="h-auto rounded-lg px-2 py-1 text-xs text-muted-foreground hover:text-foreground" variant="outline">
          {resolvedLabel}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[168px]">
        {columns.map((column) => (
          <DropdownMenuCheckboxItem
            checked={column.getIsVisible()}
            className="text-xs"
            key={column.id}
            onCheckedChange={(checked) => column.toggleVisibility(checked === true)}
            onSelect={(event) => event.preventDefault()}
          >
            {typeof column.columnDef.header === 'string' ? column.columnDef.header : column.id}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
