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
import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import {
  DataTableRowActions,
  type DataTableRowActionItem,
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
import { useI18n } from '@/lib/i18n'
import { getManifestConflicts, getManifestRows, resolveManifestConflict } from '@/lib/api'
import type { ManifestConflict, ManifestRow } from '@/lib/types'
import { createRouteIntentPrefetchHandlers } from '@/routes/lazy-routes'

const PreviewDrawer = lazy(() => import('@/components/manifest/preview-drawer').then((module) => ({ default: module.PreviewDrawer })))

const defaultColumns: VisibilityState = {
  severity: true,
  type: true,
  status: true,
  reason: true,
  source_path: true,
  target_path: true,
  row_id: true,
  manual_target: true,
}

export function ConflictPage() {
  const { t } = useI18n()
  const { jobId = '' } = useParams()
  const [rows, setRows] = useState<ManifestRow[]>([])
  const [conflicts, setConflicts] = useState<ManifestConflict[]>([])
  const [previewRowId, setPreviewRowId] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [statusFilter, setStatusFilter] = useState<'all' | 'open' | 'resolved' | 'ignored'>('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [manualTargetById, setManualTargetById] = useState<Record<string, string>>({})
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(defaultColumns)
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})
  const [focusedConflictId, setFocusedConflictId] = useState('')

  const { runAction, hasBusy, isBusy } = useRowActions()

  const refreshData = useCallback(async () => {
    if (!jobId) {
      return
    }
    setLoading(true)
    setError('')
    try {
      const [nextRows, nextConflicts] = await Promise.all([getManifestRows(jobId), getManifestConflicts(jobId)])
      setRows(nextRows)
      setConflicts(nextConflicts)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t('conflicts.error.loadFailed'))
    } finally {
      setLoading(false)
    }
  }, [jobId, t])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshData()
    }, 0)
    return () => {
      window.clearTimeout(timer)
    }
  }, [refreshData])

  const selectedRow = useMemo(() => rows.find((row) => row.id === previewRowId) ?? null, [previewRowId, rows])
  const availableTypes = useMemo(() => ['all', ...new Set(conflicts.map((item) => item.type))], [conflicts])
  const conflictCount = conflicts.length
  const openCount = useMemo(() => conflicts.filter((item) => item.status === 'open').length, [conflicts])
  const resolvedCount = useMemo(() => conflicts.filter((item) => item.status === 'resolved').length, [conflicts])

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

  const handleResolve = useCallback(async (
    conflict: ManifestConflict,
    action: 'accept_suggestion' | 'ignore' | 'manual_target',
    manualTarget?: string,
  ) => {
    const actionKey = `${conflict.id}:${action}`
    const success = await runAction(actionKey, async () => {
      const ok = await resolveManifestConflict(jobId, conflict.id, action, manualTarget)
      if (!ok) {
        throw new Error('resolve failed')
      }
    })

    if (!success) {
      toast.warning(t('conflicts.toast.resolveRejected'))
      return
    }

    toast.success(t('conflicts.toast.resolveSubmitted'))
    await refreshData()
  }, [jobId, refreshData, runAction, t])

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
        header: ({ column }) => (
          <DataTableSortableHeader label={t('conflicts.table.severity')} onToggle={() => column.toggleSorting(column.getIsSorted() === 'asc')} sorted={column.getIsSorted()} />
        ),
        cell: ({ row }) => <Badge variant={row.original.severity === 'error' ? 'destructive' : 'warning'}>{row.original.severity}</Badge>,
      },
      {
        accessorKey: 'type',
        header: ({ column }) => (
          <DataTableSortableHeader label={t('conflicts.table.type')} onToggle={() => column.toggleSorting(column.getIsSorted() === 'asc')} sorted={column.getIsSorted()} />
        ),
        cell: ({ row }) => <Badge variant="outline">{row.original.type}</Badge>,
      },
      {
        accessorKey: 'status',
        header: ({ column }) => (
          <DataTableSortableHeader label={t('conflicts.table.status')} onToggle={() => column.toggleSorting(column.getIsSorted() === 'asc')} sorted={column.getIsSorted()} />
        ),
        cell: ({ row }) => <Badge variant="secondary">{row.original.status}</Badge>,
      },
      {
        accessorKey: 'reason',
        header: ({ column }) => (
          <DataTableSortableHeader label={t('conflicts.table.reason')} onToggle={() => column.toggleSorting(column.getIsSorted() === 'asc')} sorted={column.getIsSorted()} />
        ),
        cell: ({ row }) => <p className="max-w-[320px] truncate">{row.original.reason}</p>,
      },
      {
        accessorKey: 'source_path',
        header: t('conflicts.table.source'),
        cell: ({ row }) => <p className="max-w-[300px] truncate text-xs text-muted-foreground">{row.original.source_path}</p>,
      },
      {
        accessorKey: 'target_path',
        header: t('conflicts.table.target'),
        cell: ({ row }) => <p className="max-w-[300px] truncate text-xs text-muted-foreground">{row.original.target_path || '-'}</p>,
      },
      {
        accessorKey: 'row_id',
        header: t('conflicts.table.row'),
        cell: ({ row }) => <p className="max-w-[120px] truncate text-xs text-muted-foreground">{row.original.row_id || '-'}</p>,
      },
      {
        id: 'manual_target',
        enableSorting: false,
        header: t('conflicts.table.manualTarget'),
        cell: ({ row }) => (
          <Input
            onChange={(event) =>
              setManualTargetById((prev) => ({
                ...prev,
                [row.original.id]: event.target.value,
              }))
            }
            onClick={(event) => event.stopPropagation()}
            placeholder={t('conflicts.table.manualTargetPlaceholder')}
            value={manualTargetById[row.original.id] ?? row.original.suggested_target ?? ''}
          />
        ),
      },
      {
        id: 'actions',
        enableSorting: false,
        enableHiding: false,
        header: t('conflicts.table.actions'),
        cell: ({ row }) => {
          const conflict = row.original
          const manualTarget = (manualTargetById[conflict.id] ?? conflict.suggested_target ?? '').trim()
          const items: DataTableRowActionItem[] = [
            {
              key: 'accept',
              label: t('conflicts.action.accept'),
              disabled: hasBusy || isBusy(`${conflict.id}:accept_suggestion`),
              onSelect: () => {
                void handleResolve(conflict, 'accept_suggestion')
              },
            },
            {
              key: 'manual',
              label: t('conflicts.action.manualTarget'),
              disabled: hasBusy || manualTarget.length === 0 || isBusy(`${conflict.id}:manual_target`),
              onSelect: () => {
                void handleResolve(conflict, 'manual_target', manualTarget)
              },
            },
            {
              key: 'ignore',
              label: t('conflicts.action.ignore'),
              disabled: hasBusy || isBusy(`${conflict.id}:ignore`),
              onSelect: () => {
                void handleResolve(conflict, 'ignore')
              },
            },
          ]

          if (conflict.row_id) {
            items.push({
              key: 'preview',
              label: t('conflicts.action.previewRow'),
              onSelect: () => {
                setPreviewRowId(conflict.row_id)
                setPreviewOpen(true)
              },
            })
          }

          return (
            <div className="text-right">
              <DataTableRowActions items={items} />
            </div>
          )
        },
        meta: {
          headerClassName: 'text-right',
          cellClassName: 'text-right',
        },
      },
    ],
    [handleResolve, hasBusy, isBusy, manualTargetById, t],
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
    return table.getRowModel().rows[0]?.original ?? null
  }, [conflicts, focusedConflictId, selectedConflicts, table])

  useEffect(() => {
    if (!focusedConflict && focusedConflictId.length > 0) {
      setFocusedConflictId('')
    }
  }, [focusedConflict, focusedConflictId])

  const reviewPrefetch = createRouteIntentPrefetchHandlers('review')
  const applyPrefetch = createRouteIntentPrefetchHandlers('apply')

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
      toast.warning(t('conflicts.toast.batchPartial'))
      return
    }

    toast.success(t('conflicts.toast.batchSuccess', { count: selectedConflicts.length }))
    table.resetRowSelection()
    await refreshData()
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>{t('conflicts.title')}</CardTitle>
          <CardDescription>{t('conflicts.description', { jobId: jobId || 'unknown' })}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
            <StatBlock label={t('conflicts.stats.total')} value={String(conflictCount)} />
            <StatBlock label={t('conflicts.stats.open')} tone="warning" value={String(openCount)} />
            <StatBlock label={t('conflicts.stats.resolved')} tone="success" value={String(resolvedCount)} />
            <StatBlock label={t('conflicts.stats.relatedRows')} value={String(rows.length)} />
          </div>

          <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
            <Select onChange={(event) => setStatusFilter(event.target.value as 'all' | 'open' | 'resolved' | 'ignored')} value={statusFilter}>
              <option value="all">{t('conflicts.filters.status.all')}</option>
              <option value="open">{t('conflicts.filters.status.open')}</option>
              <option value="resolved">{t('conflicts.filters.status.resolved')}</option>
              <option value="ignored">{t('conflicts.filters.status.ignored')}</option>
            </Select>
            <Select onChange={(event) => setTypeFilter(event.target.value)} value={typeFilter}>
              {availableTypes.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
            <Input className="md:col-span-2" onChange={(event) => setQuery(event.target.value)} placeholder={t('conflicts.filters.searchPlaceholder')} value={query} />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={() => {
                void refreshData()
              }}
              size="sm"
              variant="outline"
            >
              {t('conflicts.cta.refresh')}
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link {...reviewPrefetch} to={`/review/${jobId}`}>
                {t('conflicts.cta.backReview')}
              </Link>
            </Button>
            <Button asChild size="sm">
              <Link {...applyPrefetch} to={`/apply/${jobId}`}>
                {t('conflicts.cta.openApply')}
              </Link>
            </Button>
            {loading ? <Badge variant="secondary">{t('conflicts.state.loading')}</Badge> : null}
            {error ? <Badge variant="destructive">{error}</Badge> : null}
          </div>

          <DataTableToolbar
            leading={
              <>
                <Button disabled={selectedConflicts.length === 0 || hasBusy} onClick={() => void handleBatch('accept_suggestion')} size="sm" variant="secondary">
                  {t('conflicts.batch.accept')}
                </Button>
                <Button disabled={selectedConflicts.length === 0 || hasBusy} onClick={() => void handleBatch('ignore')} size="sm" variant="outline">
                  {t('conflicts.batch.ignore')}
                </Button>
              </>
            }
            onClearSelection={() => table.resetRowSelection()}
            selectionCount={selectedConflicts.length}
            totalCount={table.getFilteredRowModel().rows.length}
            trailing={<DataTableViewOptions label={t('conflicts.table.columns')} table={table} />}
          />

          <DataTableShell
            emptyDescription={t('conflicts.table.emptyDescription')}
            emptyTitle={t('conflicts.table.emptyTitle')}
            onRowClick={(row) => {
              row.toggleSelected(true)
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
              <p className="mt-1 text-xs text-muted-foreground">{t('conflicts.detail.source', { value: focusedConflict.source_path })}</p>
              <p className="text-xs text-muted-foreground">{t('conflicts.detail.target', { value: focusedConflict.target_path || '-' })}</p>
              {focusedConflict.suggested_target ? <p className="text-xs text-muted-foreground">{t('conflicts.detail.suggested', { value: focusedConflict.suggested_target })}</p> : null}

              <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-[1fr_auto_auto_auto_auto]">
                <Input
                  onChange={(event) =>
                    setManualTargetById((prev) => ({
                      ...prev,
                      [focusedConflict.id]: event.target.value,
                    }))
                  }
                  placeholder={t('conflicts.detail.manualTargetPlaceholder')}
                  value={manualTargetById[focusedConflict.id] ?? focusedConflict.suggested_target ?? ''}
                />
                <Button
                  disabled={hasBusy}
                  onClick={() => {
                    void handleResolve(focusedConflict, 'accept_suggestion')
                  }}
                  size="sm"
                  variant="secondary"
                >
                  {t('conflicts.action.accept')}
                </Button>
                <Button
                  disabled={hasBusy || (manualTargetById[focusedConflict.id] ?? '').trim().length === 0}
                  onClick={() => {
                    void handleResolve(focusedConflict, 'manual_target', (manualTargetById[focusedConflict.id] ?? '').trim())
                  }}
                  size="sm"
                  variant="outline"
                >
                  {t('conflicts.action.manualTarget')}
                </Button>
                <Button
                  disabled={hasBusy}
                  onClick={() => {
                    void handleResolve(focusedConflict, 'ignore')
                  }}
                  size="sm"
                  variant="ghost"
                >
                  {t('conflicts.action.ignore')}
                </Button>
                {focusedConflict.row_id ? (
                  <Button
                    onClick={() => {
                      setPreviewRowId(focusedConflict.row_id)
                      setPreviewOpen(true)
                    }}
                    size="sm"
                    variant="outline"
                  >
                    {t('conflicts.action.previewRow')}
                  </Button>
                ) : null}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Suspense fallback={null}>
        {selectedRow ? (
          <PreviewDrawer
            editedRow={null}
            jobId={jobId}
            onOpenChange={(open) => {
              setPreviewOpen(open)
              if (!open) {
                setPreviewRowId('')
              }
            }}
            open={previewOpen}
            row={selectedRow}
          />
        ) : null}
      </Suspense>
    </div>
  )
}

function StatBlock({ label, value, tone = 'default' }: { label: string; value: string; tone?: 'default' | 'warning' | 'success' }) {
  return (
    <div className="rounded-xl border border-border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={tone === 'warning' ? 'text-lg font-semibold text-warning-ink' : tone === 'success' ? 'text-lg font-semibold text-success' : 'text-lg font-semibold'}>
        {value}
      </p>
    </div>
  )
}
