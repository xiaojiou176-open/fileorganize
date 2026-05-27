import type { ColumnDef } from '@tanstack/react-table'
import { getCoreRowModel, useReactTable } from '@tanstack/react-table'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { DataTableShell } from '@/components/data-table/data-table-shell'

interface TestRow {
  name: string
}

function DataTableShellHarness({ onRowOpen }: { onRowOpen: (row: TestRow) => void }) {
  const data: TestRow[] = [{ name: 'alpha' }]
  const columns: ColumnDef<TestRow>[] = [
    {
      accessorKey: 'name',
      header: 'Name',
      cell: ({ row }) => row.original.name,
    },
  ]

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  return <DataTableShell onRowClick={(row) => onRowOpen(row.original)} table={table} />
}

describe('DataTableShell keyboard accessibility', () => {
  it('triggers row click via Enter and Space', () => {
    const onRowOpen = vi.fn()

    render(<DataTableShellHarness onRowOpen={onRowOpen} />)

    const row = screen.getByText('alpha').closest('tr')
    if (!row) {
      throw new Error('Expected data row to exist')
    }

    expect(row).toHaveAttribute('tabindex', '0')

    fireEvent.keyDown(row, { key: 'Enter' })
    fireEvent.keyDown(row, { key: ' ' })

    expect(onRowOpen).toHaveBeenCalledTimes(2)
  })
})
