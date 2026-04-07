import {
  type ColumnDef,
  type ColumnFiltersState,
  type RowSelectionState,
  type SortingState,
  type VisibilityState,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import {
  DataTableRowSelectionCell,
  DataTableRowSelectionHeader,
  DataTableShell,
  DataTableSortableHeader,
  DataTableToolbar,
  DataTableViewOptions,
  useRowActions,
} from '@/components/data-table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { resolveManifestConflict } from '@/lib/api'
import type { ManifestConflict } from '@/lib/types'

interface ConflictCenterProps {
  jobId: string
  conflicts: ManifestConflict[]
  onRefresh: () => void
  onPreviewRowId?: (rowId: string) => void
}

const defaultColumns: VisibilityState = {
  source_path: true,
  target_path: true,
  reason: true,
  row_id: true,
}

export function ConflictCenter({ jobId, conflicts, onRefresh, onPreviewRowId }: ConflictCenterProps) {
  const [statusFilter, setStatusFilter] = useState<'all' | 'open' | 'resolved' | 'ignored'>('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [manualTargetById, setManualTargetById] = useState<Record<string, string>>({})
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(defaultColumns)
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})
  const [focusedConflictId, setFocusedConflictId] = useState('')

  const { runAction, isBusy, hasBusy } = useRowActions()

  const availableTypes = useMemo(() => {
    return ['all', ...new Set(conflicts.map((item) => item.type))]
  }, [conflicts])

  useEffect(() => {
    setColumnFilters((prev) => {
      const next = prev.filter((item) => item.id !== 'status' && item.id !== 'type')
      if (statusFilter !== 'all') {
        next.push({ id: 'status', value: statusFilter })
      }
      if (typeFilter !== 'all') {
        next.push({ id: 'type', value: typeFilter })
      }
      return next
    })
  }, [statusFilter, typeFilter])

  useEffect(() => {
    setRowSelection((prev) => {
      const validIds = new Set(conflicts.map((item) => item.id))
      const next: RowSelectionState = {}
      let changed = false
      for (const [conflictId, selected] of Object.entries(prev)) {
        if (selected && validIds.has(conflictId)) {
          next[conflictId] = true
        } else if (selected) {
          changed = true
        }
      }
      return changed ? next : prev
    })
  }, [conflicts])

  const handleResolve = useCallback(
    async (conflict: ManifestConflict, action: 'accept_suggestion' | 'ignore' | 'manual_target', manualTarget?: string) => {
      const actionKey = `${conflict.id}:${action}`
      const success = await runAction(actionKey, async () => {
        const ok = await resolveManifestConflict(jobId, conflict.id, action, manualTarget)
        if (!ok) {
          throw new Error('resolve failed')
        }
      })

      if (!success) {
        toast.warning('The backend did not confirm the conflict resolution. The local view was kept unchanged.')
        return
      }

      toast.success('Conflict resolution was submitted.')
      onRefresh()
    },
    [jobId, onRefresh, runAction],
  )

  const columns = useMemo<ColumnDef<ManifestConflict>[]>(
    () => [
      {
        id: 'select',
        enableSorting: false,
        enableHiding: false,
        header: ({ table }) => <DataTableRowSelectionHeader ariaLabel="Select all conflicts" table={table} usePageRows={false} />,
        cell: ({ row }) => <DataTableRowSelectionCell ariaLabel={`Select conflict ${row.original.id}`} row={row} />,
        meta: {
          headerClassName: 'w-9',
          cellClassName: 'w-9',
        },
      },
      {
        accessorKey: 'severity',
        header: 'Severity',
        cell: ({ row }) => <Badge variant={row.original.severity === 'error' ? 'destructive' : 'warning'}>{row.original.severity}</Badge>,
      },
      {
        accessorKey: 'type',
        header: ({ column }) => (
          <DataTableSortableHeader
            label="Type"
            onToggle={() => column.toggleSorting(column.getIsSorted() === 'asc')}
            sorted={column.getIsSorted()}
          />
        ),
        cell: ({ row }) => <Badge variant="outline">{row.original.type}</Badge>,
      },
      {
        accessorKey: 'status',
        header: ({ column }) => (
          <DataTableSortableHeader
            label="Status"
            onToggle={() => column.toggleSorting(column.getIsSorted() === 'asc')}
            sorted={column.getIsSorted()}
          />
        ),
        cell: ({ row }) => <Badge variant="secondary">{row.original.status}</Badge>,
      },
      {
        accessorKey: 'reason',
        header: ({ column }) => (
          <DataTableSortableHeader
            label="Reason"
            onToggle={() => column.toggleSorting(column.getIsSorted() === 'asc')}
            sorted={column.getIsSorted()}
          />
        ),
        cell: ({ row }) => <p className="max-w-[300px] truncate">{row.original.reason}</p>,
      },
      {
        accessorKey: 'source_path',
        header: 'Source',
        cell: ({ row }) => <p className="max-w-[280px] truncate text-xs text-muted-foreground">{row.original.source_path}</p>,
      },
      {
        accessorKey: 'target_path',
        header: 'Target',
        cell: ({ row }) => <p className="max-w-[280px] truncate text-xs text-muted-foreground">{row.original.target_path || '-'}</p>,
      },
      {
        accessorKey: 'row_id',
        header: 'Row',
        cell: ({ row }) => <p className="max-w-[120px] truncate text-xs text-muted-foreground">{row.original.row_id || '-'}</p>,
      },
      {
        id: 'manual_target',
        enableSorting: false,
        header: 'Manual Target',
        cell: ({ row }) => (
          <Input
            aria-label={`Manual target path ${row.original.source_path}`}
            onChange={(event) =>
              setManualTargetById((prev) => ({
                ...prev,
                [row.original.id]: event.target.value,
              }))
            }
            onClick={(event) => event.stopPropagation()}
            placeholder="Manual target path"
            value={manualTargetById[row.original.id] ?? row.original.suggested_target ?? ''}
          />
        ),
      },
      {
        id: 'actions',
        enableSorting: false,
        enableHiding: false,
        header: 'Actions',
        cell: ({ row }) => {
          const conflict = row.original
          const manualTarget = (manualTargetById[conflict.id] ?? conflict.suggested_target ?? '').trim()
          return (
            <div className="flex flex-wrap justify-end gap-1">
              <Button
                disabled={isBusy(`${conflict.id}:accept_suggestion`) || hasBusy}
                onClick={(event) => {
                  event.stopPropagation()
                  void handleResolve(conflict, 'accept_suggestion')
                }}
                size="sm"
                variant="secondary"
              >
                Accept
              </Button>
              <Button
                disabled={manualTarget.length === 0 || isBusy(`${conflict.id}:manual_target`) || hasBusy}
                onClick={(event) => {
                  event.stopPropagation()
                  void handleResolve(conflict, 'manual_target', manualTarget)
                }}
                size="sm"
                variant="outline"
              >
                Manual
              </Button>
              <Button
                disabled={isBusy(`${conflict.id}:ignore`) || hasBusy}
                onClick={(event) => {
                  event.stopPropagation()
                  void handleResolve(conflict, 'ignore')
                }}
                size="sm"
                variant="ghost"
              >
                Ignore
              </Button>
              {conflict.row_id ? (
                <Button
                  onClick={(event) => {
                    event.stopPropagation()
                    onPreviewRowId?.(conflict.row_id)
                  }}
                  size="sm"
                  variant="ghost"
                >
                  Preview
                </Button>
              ) : null}
            </div>
          )
        },
        meta: {
          headerClassName: 'text-right',
          cellClassName: 'text-right',
        },
      },
    ],
    [handleResolve, hasBusy, isBusy, manualTargetById, onPreviewRowId],
  )

  const table = useReactTable({
    data: conflicts,
    columns,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
      globalFilter: query,
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    onGlobalFilterChange: setQuery,
    getRowId: (row) => row.id,
    enableRowSelection: true,
    autoResetAll: false,
    globalFilterFn: (row, _columnId, filterValue) => {
      const keyword = String(filterValue ?? '').trim().toLowerCase()
      if (keyword.length === 0) {
        return true
      }
      const haystack = `${row.original.reason} ${row.original.source_path} ${row.original.target_path} ${row.original.type}`.toLowerCase()
      return haystack.includes(keyword)
    },
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  const selectedConflicts = table.getSelectedRowModel().rows.map((row) => row.original)

  const focusedConflict = useMemo(() => {
    if (focusedConflictId.length > 0) {
      const exact = conflicts.find((item) => item.id === focusedConflictId)
      if (exact) {
        return exact
      }
    }
    const selectedId = selectedConflicts[0]?.id
    if (selectedId) {
      return conflicts.find((item) => item.id === selectedId) ?? null
    }
    const firstVisible = table.getRowModel().rows[0]?.original
    return firstVisible ?? null
  }, [conflicts, focusedConflictId, selectedConflicts, table])

  useEffect(() => {
    if (!focusedConflict && focusedConflictId) {
      setFocusedConflictId('')
    }
  }, [focusedConflict, focusedConflictId])

  async function handleBatch(action: 'accept_suggestion' | 'ignore') {
    if (selectedConflicts.length === 0) {
      return
    }

    const key = `batch:${action}`
    const success = await runAction(key, async () => {
      await Promise.all(
        selectedConflicts.map(async (conflict) => {
          const ok = await resolveManifestConflict(jobId, conflict.id, action)
          if (!ok) {
            throw new Error(conflict.id)
          }
        }),
      )
    })

    if (!success) {
      toast.warning('Batch processing did not fully succeed. Retry or handle the conflicts one by one.')
      return
    }

    toast.success(`Processed ${selectedConflicts.length} conflicts.`)
    table.resetRowSelection()
    onRefresh()
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Conflict Center</CardTitle>
        <CardDescription>Resolve duplicate paths, target conflicts, and rule exceptions in one place.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
          <Select aria-label="Filter conflicts by status" onValueChange={(value) => setStatusFilter(value as 'all' | 'open' | 'resolved' | 'ignored')} value={statusFilter}>
            <option value="all">All statuses</option>
            <option value="open">Open</option>
            <option value="resolved">Resolved</option>
            <option value="ignored">Ignored</option>
          </Select>
          <Select aria-label="Filter conflicts by type" onValueChange={setTypeFilter} value={typeFilter}>
            {availableTypes.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </Select>
          <Input className="md:col-span-2" onChange={(event) => setQuery(event.target.value)} placeholder="Search conflict reason or path" value={query} />
        </div>

        <DataTableToolbar
          leading={
            <>
              <Button disabled={selectedConflicts.length === 0 || hasBusy} onClick={() => void handleBatch('accept_suggestion')} size="sm" variant="secondary">
                Accept Selected
              </Button>
              <Button disabled={selectedConflicts.length === 0 || hasBusy} onClick={() => void handleBatch('ignore')} size="sm" variant="outline">
                Ignore Selected
              </Button>
            </>
          }
          onClearSelection={() => table.resetRowSelection()}
          selectionCount={selectedConflicts.length}
          totalCount={table.getFilteredRowModel().rows.length}
          trailing={<DataTableViewOptions label="Columns" table={table} />}
        />

        <DataTableShell
          emptyDescription="No conflicts match the current filters."
          emptyTitle="No conflicts"
          onRowClick={(row) => {
            setFocusedConflictId(row.original.id)
          }}
          table={table}
        />

        {focusedConflict ? (
          <div className="rounded-xl border border-border p-3 text-sm">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Badge variant={focusedConflict.severity === 'error' ? 'destructive' : 'warning'}>{focusedConflict.severity}</Badge>
              <Badge variant="outline">{focusedConflict.type}</Badge>
              <Badge variant="secondary">{focusedConflict.status}</Badge>
            </div>
            <p className="font-medium">{focusedConflict.reason}</p>
            <p className="mt-1 text-xs text-muted-foreground">source: {focusedConflict.source_path}</p>
            <p className="text-xs text-muted-foreground">target: {focusedConflict.target_path || '-'}</p>
            {focusedConflict.suggested_target ? <p className="text-xs text-muted-foreground">suggested: {focusedConflict.suggested_target}</p> : null}

            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-[1fr_auto_auto_auto_auto]">
              <Input
                aria-label={`Manual target path ${focusedConflict.source_path}`}
                onChange={(event) =>
                  setManualTargetById((prev) => ({
                    ...prev,
                    [focusedConflict.id]: event.target.value,
                  }))
                }
                placeholder="Manual target path (optional)"
                value={manualTargetById[focusedConflict.id] ?? focusedConflict.suggested_target ?? ''}
              />
              <Button
                disabled={hasBusy}
                onClick={() => void handleResolve(focusedConflict, 'accept_suggestion')}
                size="sm"
                variant="secondary"
              >
                Accept Suggestion
              </Button>
              <Button
                disabled={hasBusy || (manualTargetById[focusedConflict.id] ?? '').trim().length === 0}
                onClick={() => void handleResolve(focusedConflict, 'manual_target', (manualTargetById[focusedConflict.id] ?? '').trim())}
                size="sm"
                variant="outline"
              >
                Use Manual Target
              </Button>
              <Button disabled={hasBusy} onClick={() => void handleResolve(focusedConflict, 'ignore')} size="sm" variant="ghost">
                Ignore
              </Button>
              {focusedConflict.row_id ? (
                <Button
                  onClick={() => {
                    onPreviewRowId?.(focusedConflict.row_id)
                  }}
                  size="sm"
                  variant="outline"
                >
                  Preview Related Row
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
