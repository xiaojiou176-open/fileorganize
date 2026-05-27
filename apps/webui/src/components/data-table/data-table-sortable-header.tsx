import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

interface DataTableSortableHeaderProps {
  label: string
  sorted: false | 'asc' | 'desc'
  onToggle: () => void
  className?: string
}

export function DataTableSortableHeader({ label, sorted, onToggle, className }: DataTableSortableHeaderProps) {
  return (
    <Button
      className={cn('h-8 items-center gap-1 px-2 py-1 text-left text-xs font-medium text-muted-foreground hover:text-foreground', className)}
      onClick={onToggle}
      size="sm"
      variant="ghost"
    >
      <span>{label}</span>
      <span className="text-[11px]">{sorted === 'asc' ? '↑' : sorted === 'desc' ? '↓' : '↕'}</span>
    </Button>
  )
}
