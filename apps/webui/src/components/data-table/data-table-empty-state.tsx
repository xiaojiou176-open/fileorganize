interface DataTableEmptyStateProps {
  title: string
  description?: string
}

export function DataTableEmptyState({ title, description }: DataTableEmptyStateProps) {
  return (
    <div className="grid gap-1 py-6 text-center">
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description ? <p className="text-xs text-muted-foreground">{description}</p> : null}
    </div>
  )
}
