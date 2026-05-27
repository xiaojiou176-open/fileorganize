import { flexRender, type Row, type Table as TanStackTable } from '@tanstack/react-table'

import { DataTableEmptyState } from '@/components/data-table/data-table-empty-state'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableWrapper } from '@/components/ui/table'
import { useI18n } from '@/lib/i18n'
import { cn } from '@/lib/utils'

interface ColumnMeta {
  headerClassName?: string
  cellClassName?: string
}

interface DataTableShellProps<TData> {
  table: TanStackTable<TData>
  onRowClick?: (row: Row<TData>) => void
  getRowClassName?: (row: Row<TData>) => string
  emptyTitle?: string
  emptyDescription?: string
  className?: string
}

function getColumnMeta(meta: unknown): ColumnMeta {
  if (typeof meta !== 'object' || meta === null || Array.isArray(meta)) {
    return {}
  }
  return meta as ColumnMeta
}

export function DataTableShell<TData>({
  table,
  onRowClick,
  getRowClassName,
  emptyTitle,
  emptyDescription,
  className,
}: DataTableShellProps<TData>) {
  const { t } = useI18n()
  const rows = table.getRowModel().rows
  const visibleColumnsCount = table.getVisibleLeafColumns().length
  const resolvedEmptyTitle = emptyTitle ?? t('dataTable.empty.noData')

  return (
    <TableWrapper className={className}>
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow className="hover:bg-transparent" key={headerGroup.id}>
              {headerGroup.headers.map((header) => {
                const meta = getColumnMeta(header.column.columnDef.meta)
                return (
                  <TableHead className={cn(meta.headerClassName)} key={header.id}>
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                )
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {rows.length > 0 ? (
            rows.map((row) => (
              <TableRow
                className={cn(
                  row.getIsSelected() ? 'bg-primary/5' : '',
                  onRowClick ? 'cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60' : '',
                  getRowClassName?.(row),
                )}
                data-state={row.getIsSelected() ? 'selected' : undefined}
                key={row.id}
                onClick={() => {
                  onRowClick?.(row)
                }}
                onKeyDown={
                  onRowClick
                    ? (event) => {
                        if (event.target !== event.currentTarget) {
                          return
                        }
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          onRowClick(row)
                        }
                      }
                    : undefined
                }
                tabIndex={onRowClick ? 0 : undefined}
              >
                {row.getVisibleCells().map((cell) => {
                  const meta = getColumnMeta(cell.column.columnDef.meta)
                  return (
                    <TableCell className={cn(meta.cellClassName)} key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  )
                })}
              </TableRow>
            ))
          ) : (
            <TableRow className="hover:bg-transparent">
              <TableCell className="p-0" colSpan={visibleColumnsCount || 1}>
                <DataTableEmptyState description={emptyDescription} title={resolvedEmptyTitle} />
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </TableWrapper>
  )
}
