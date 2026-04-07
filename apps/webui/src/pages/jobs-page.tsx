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
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import {
  DataTableRowActions,
  DataTableRowSelectionCell,
  DataTableShell,
  DataTableSortableHeader,
  DataTableToolbar,
  DataTableViewOptions,
} from '@/components/data-table'
import { LogPanel } from '@/components/observability/log-panel'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { cancelJob, retryJob } from '@/lib/api'
import { useLiveJob } from '@/hooks/use-live-job'
import { useLiveJobs } from '@/hooks/use-live-jobs'
import { useI18n } from '@/lib/i18n'
import type { Job } from '@/lib/types'
import { formatDate, progressToPercent } from '@/lib/utils'
import { createRouteIntentPrefetchHandlers } from '@/routes/lazy-routes'

function statusVariant(status: Job['status']): 'secondary' | 'success' | 'destructive' | 'outline' | 'warning' {
  if (status === 'succeeded') {
    return 'success'
  }
  if (status === 'failed') {
    return 'destructive'
  }
  if (status === 'running') {
    return 'secondary'
  }
  if (status === 'cancelling') {
    return 'warning'
  }
  if (status === 'cancelled') {
    return 'outline'
  }
  return 'secondary'
}

const defaultColumns: VisibilityState = {
  kind: true,
  status: true,
  phase: true,
  progress: true,
  started_at: true,
}

export function JobsPage() {
  const { t } = useI18n()
  const [queryText, setQueryText] = useState('')
  const [kindFilter, setKindFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(defaultColumns)
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})
  const [actionFeedback, setActionFeedback] = useState<{ level: 'success' | 'error'; message: string } | null>(null)
  const [pendingCancelIds, setPendingCancelIds] = useState<Record<string, boolean>>({})
  const [pendingRetryIds, setPendingRetryIds] = useState<Record<string, boolean>>({})
  const pendingCancelIdsRef = useRef<Record<string, boolean>>({})
  const pendingRetryIdsRef = useRef<Record<string, boolean>>({})
  const hasInitializedSelectionRef = useRef(false)

  const { jobs, state, error, refresh } = useLiveJobs()

  useEffect(() => {
    pendingCancelIdsRef.current = pendingCancelIds
  }, [pendingCancelIds])

  useEffect(() => {
    pendingRetryIdsRef.current = pendingRetryIds
  }, [pendingRetryIds])

  const formatJobKind = useCallback((kind: Job['kind']) => {
    if (kind === 'analyze') {
      return t('jobs.kind.analyze')
    }
    if (kind === 'apply') {
      return t('jobs.kind.apply')
    }
    return t('jobs.kind.rollback')
  }, [t])

  const formatJobStatus = useCallback((status: Job['status']) => {
    if (status === 'queued') {
      return t('jobs.status.queued')
    }
    if (status === 'running') {
      return t('jobs.status.running')
    }
    if (status === 'cancelling') {
      return t('jobs.status.cancelling')
    }
    if (status === 'succeeded') {
      return t('jobs.status.succeeded')
    }
    if (status === 'failed') {
      return t('jobs.status.failed')
    }
    if (status === 'cancelled') {
      return t('jobs.status.cancelled')
    }
    return status
  }, [t])

  const handleCancel = useCallback(async (jobId: string) => {
    if (pendingCancelIdsRef.current[jobId] || pendingRetryIdsRef.current[jobId]) {
      return
    }
    setPendingCancelIds((prev) => ({ ...prev, [jobId]: true }))
    try {
      await cancelJob(jobId)
      await refresh()
      const message = t('jobs.toast.cancelSubmitted')
      setActionFeedback({ level: 'success', message })
      toast.success(message)
    } catch (error) {
      const message = error instanceof Error ? error.message : t('jobs.toast.cancelFailed')
      setActionFeedback({ level: 'error', message })
      toast.error(message)
    } finally {
      setPendingCancelIds((prev) => {
        const next = { ...prev }
        delete next[jobId]
        return next
      })
    }
  }, [refresh, t])

  const handleRetry = useCallback(async (jobId: string) => {
    if (pendingCancelIdsRef.current[jobId] || pendingRetryIdsRef.current[jobId]) {
      return
    }
    setPendingRetryIds((prev) => ({ ...prev, [jobId]: true }))
    try {
      await retryJob(jobId)
      await refresh()
      const message = t('jobs.toast.retrySubmitted')
      setActionFeedback({ level: 'success', message })
      toast.success(message)
    } catch (error) {
      const message = error instanceof Error ? error.message : t('jobs.toast.retryFailed')
      setActionFeedback({ level: 'error', message })
      toast.error(message)
    } finally {
      setPendingRetryIds((prev) => {
        const next = { ...prev }
        delete next[jobId]
        return next
      })
    }
  }, [refresh, t])

  useEffect(() => {
    setColumnFilters((prev) => {
      const next = prev.filter((item) => item.id !== 'kind' && item.id !== 'status')
      if (kindFilter !== 'all') {
        next.push({ id: 'kind', value: kindFilter })
      }
      if (statusFilter !== 'all') {
        next.push({ id: 'status', value: statusFilter })
      }
      return next
    })
  }, [kindFilter, statusFilter])

  useEffect(() => {
    setRowSelection((prev) => {
      const validIds = new Set(jobs.map((job) => job.id))
      const selectedId = Object.keys(prev).find((id) => prev[id])
      if (selectedId && validIds.has(selectedId)) {
        return prev
      }
      const fallback = jobs[0]?.id
      if (!fallback) {
        return {}
      }
      if (hasInitializedSelectionRef.current) {
        return prev
      }
      hasInitializedSelectionRef.current = true
      return { [fallback]: true }
    })
  }, [jobs])

  const selectedJobId = useMemo(() => Object.keys(rowSelection).find((id) => rowSelection[id]) ?? '', [rowSelection])
  const selectedFromList = jobs.find((job) => job.id === selectedJobId) ?? null
  const { job: selectedLiveJob, events, state: selectedState, refresh: refreshSelected } = useLiveJob(selectedJobId, selectedJobId.length > 0)
  const selected = selectedLiveJob ?? selectedFromList

  const reviewPrefetch = createRouteIntentPrefetchHandlers('review')

  const columns = useMemo<ColumnDef<Job>[]>(
    () => [
      {
        id: 'select',
        enableSorting: false,
        enableHiding: false,
        header: () => <span className="sr-only">{t('jobs.table.select')}</span>,
        cell: ({ row }) => <DataTableRowSelectionCell ariaLabel={t('jobs.table.selectRow', { id: row.original.id })} row={row} />,
        meta: {
          headerClassName: 'w-9',
          cellClassName: 'w-9',
        },
      },
      {
        accessorKey: 'id',
        header: ({ column }) => (
          <DataTableSortableHeader label={t('jobs.table.jobId')} onToggle={() => column.toggleSorting(column.getIsSorted() === 'asc')} sorted={column.getIsSorted()} />
        ),
        cell: ({ row }) => <p className="max-w-[260px] truncate font-medium">{row.original.id}</p>,
      },
      {
        accessorKey: 'kind',
        header: ({ column }) => (
          <DataTableSortableHeader label={t('jobs.table.kind')} onToggle={() => column.toggleSorting(column.getIsSorted() === 'asc')} sorted={column.getIsSorted()} />
        ),
        cell: ({ row }) => formatJobKind(row.original.kind),
      },
      {
        accessorKey: 'status',
        header: ({ column }) => (
          <DataTableSortableHeader label={t('jobs.table.status')} onToggle={() => column.toggleSorting(column.getIsSorted() === 'asc')} sorted={column.getIsSorted()} />
        ),
        cell: ({ row }) => <Badge variant={statusVariant(row.original.status)}>{formatJobStatus(row.original.status)}</Badge>,
      },
      {
        accessorKey: 'phase',
        header: t('jobs.table.phase'),
        cell: ({ row }) => <p className="max-w-[180px] truncate">{row.original.phase}</p>,
      },
      {
        id: 'progress',
        accessorFn: (row) => progressToPercent(row.progress),
        header: ({ column }) => (
          <DataTableSortableHeader label={t('jobs.table.progress')} onToggle={() => column.toggleSorting(column.getIsSorted() === 'asc')} sorted={column.getIsSorted()} />
        ),
        cell: ({ getValue }) => `${getValue<number>()}%`,
      },
      {
        accessorKey: 'started_at',
        header: ({ column }) => (
          <DataTableSortableHeader label={t('jobs.table.started')} onToggle={() => column.toggleSorting(column.getIsSorted() === 'asc')} sorted={column.getIsSorted()} />
        ),
        cell: ({ row }) => formatDate(row.original.started_at),
      },
      {
        id: 'actions',
        enableSorting: false,
        enableHiding: false,
        header: () => <span className="text-right">{t('jobs.table.action')}</span>,
        cell: ({ row }) => (
          <div className="flex items-center justify-end gap-1">
            <DataTableRowActions
              items={[
                {
                  key: 'logs',
                  label: t('jobs.table.viewLogs'),
                  onSelect: () => row.toggleSelected(true),
                },
                ...(row.original.status === 'queued' || row.original.status === 'running' || row.original.status === 'cancelling'
                  ? [
                      {
                        key: 'cancel',
                        label: pendingCancelIds[row.original.id] || row.original.status === 'cancelling' ? t('jobs.table.cancelling') : t('jobs.table.cancelJob'),
                        disabled:
                          row.original.status === 'cancelling' || Boolean(pendingCancelIds[row.original.id]) || Boolean(pendingRetryIds[row.original.id]),
                        destructive: true,
                        onSelect: () => {
                          void handleCancel(row.original.id)
                        },
                      },
                    ]
                  : []),
                ...(row.original.status === 'failed' || row.original.status === 'cancelled' || row.original.status === 'succeeded'
                  ? [
                      {
                        key: 'retry',
                        label: pendingRetryIds[row.original.id] ? t('jobs.table.retrying') : t('jobs.table.retryJob'),
                        disabled: Boolean(pendingCancelIds[row.original.id]) || Boolean(pendingRetryIds[row.original.id]),
                        onSelect: () => {
                          void handleRetry(row.original.id)
                        },
                      },
                    ]
                  : []),
              ]}
            />
            <Button asChild size="sm" variant="outline">
              <Link {...reviewPrefetch} onClick={(event) => event.stopPropagation()} to={`/review/${row.original.id}`}>
                {t('jobs.table.review')}
              </Link>
            </Button>
          </div>
        ),
        meta: {
          headerClassName: 'text-right',
          cellClassName: 'text-right',
        },
      },
    ],
    [formatJobKind, formatJobStatus, handleCancel, handleRetry, pendingCancelIds, pendingRetryIds, reviewPrefetch, t],
  )

  const table = useReactTable({
    data: jobs,
    columns,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
      globalFilter: queryText,
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    onGlobalFilterChange: setQueryText,
    getRowId: (row) => row.id,
    enableRowSelection: true,
    enableMultiRowSelection: false,
    autoResetAll: false,
    globalFilterFn: (row, _columnId, filterValue) => {
      const keyword = String(filterValue ?? '').trim().toLowerCase()
      if (keyword.length === 0) {
        return true
      }
      return `${row.original.id} ${row.original.phase} ${row.original.status}`.toLowerCase().includes(keyword)
    },
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>{t('jobs.page.title')}</CardTitle>
          <CardDescription>{t('jobs.page.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
            <Input
              aria-label={t('jobs.filters.searchAria')}
              onChange={(event) => setQueryText(event.target.value)}
              placeholder={t('jobs.filters.searchPlaceholder')}
              value={queryText}
            />
            <NativeSelect
              aria-label={t('jobs.filters.kindAria')}
              onChange={(event) => setKindFilter(event.target.value)}
              value={kindFilter}
            >
              <option value="all">{t('jobs.filters.kindAll')}</option>
              <option value="analyze">analyze</option>
              <option value="apply">apply</option>
              <option value="rollback">rollback</option>
            </NativeSelect>
            <NativeSelect
              aria-label={t('jobs.filters.statusAria')}
              onChange={(event) => setStatusFilter(event.target.value)}
              value={statusFilter}
            >
              <option value="all">{t('jobs.filters.statusAll')}</option>
              <option value="queued">queued</option>
              <option value="running">running</option>
              <option value="cancelling">cancelling</option>
              <option value="succeeded">succeeded</option>
              <option value="failed">failed</option>
              <option value="cancelled">cancelled</option>
            </NativeSelect>
            <div className="flex items-center gap-2">
              <Badge variant={state === 'open' ? 'success' : 'warning'}>{state === 'open' ? t('jobs.connection.open') : t('jobs.connection.fallback')}</Badge>
              <Button
                onClick={() => {
                  void refresh()
                }}
                size="sm"
                variant="outline"
              >
                {t('jobs.cta.refresh')}
              </Button>
            </div>
          </div>

          <DataTableToolbar
            onClearSelection={() => table.resetRowSelection()}
            selectionCount={table.getSelectedRowModel().rows.length}
            totalCount={table.getFilteredRowModel().rows.length}
            trailing={<DataTableViewOptions label={t('dataTable.viewOptions.label')} table={table} />}
          />

          {error ? <p className="text-sm text-warning-ink">{t('jobs.error.refreshFailed', { error })}</p> : null}
          {actionFeedback ? (
            <p
              aria-live="polite"
              className={actionFeedback.level === 'error' ? 'text-sm text-destructive' : 'text-sm text-success'}
              role="status"
            >
              {actionFeedback.message}
            </p>
          ) : null}

          <DataTableShell
            emptyDescription={t('jobs.table.emptyDescription')}
            emptyTitle={t('jobs.table.emptyTitle')}
            getRowClassName={(row) => (row.getIsSelected() ? 'bg-primary/5' : '')}
            table={table}
          />
        </CardContent>
      </Card>

      <Card data-testid="current-job-card">
        <CardHeader>
          <CardTitle>{t('jobs.current.title')}</CardTitle>
          <CardDescription>{t('jobs.current.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          {selected ? (
            <>
              <div className="space-y-1">
                <p className="font-medium text-foreground">{selected.id}</p>
                <p>
                  {formatJobKind(selected.kind)} · {selected.phase}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {(selected.status === 'queued' || selected.status === 'running' || selected.status === 'cancelling') ? (
                  <Button
                    data-testid="current-job-cancel"
                    disabled={
                      selected.status === 'cancelling' || Boolean(pendingCancelIds[selected.id]) || Boolean(pendingRetryIds[selected.id])
                    }
                    onClick={() => {
                      void handleCancel(selected.id)
                    }}
                    size="sm"
                    variant="destructive"
                  >
                    {selected.status === 'cancelling' || pendingCancelIds[selected.id] ? t('jobs.table.cancelling') : t('jobs.table.cancelJob')}
                  </Button>
                ) : null}
                {(selected.status === 'failed' || selected.status === 'cancelled' || selected.status === 'succeeded') ? (
                  <Button
                    data-testid="current-job-retry"
                    disabled={Boolean(pendingCancelIds[selected.id]) || Boolean(pendingRetryIds[selected.id])}
                    onClick={() => {
                      void handleRetry(selected.id)
                    }}
                    size="sm"
                    variant="outline"
                  >
                    {pendingRetryIds[selected.id] ? t('jobs.table.retrying') : t('jobs.table.retryJob')}
                  </Button>
                ) : null}
              </div>
            </>
          ) : (
            <p>{t('jobs.current.none')}</p>
          )}
        </CardContent>
      </Card>

      <LogPanel
        connectionState={selectedState}
        description={selected ? `${formatJobKind(selected.kind)} · ${selected.phase}` : t('jobs.logs.emptyDescription')}
        events={events}
        onRefresh={() => {
          void refreshSelected()
        }}
        title={selected ? `${t('jobs.logs.title')} · ${selected.id}` : t('jobs.logs.title')}
      />
    </div>
  )
}
