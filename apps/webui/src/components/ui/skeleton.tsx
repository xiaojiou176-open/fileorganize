import { cn } from '@/lib/utils'

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn('skeleton-shimmer rounded-md bg-muted/70', className)} />
}

export function PanelSkeleton({ className, lines = 3 }: { className?: string; lines?: number }) {
  return (
    <div className={cn('space-y-2 rounded-xl border border-border/60 bg-card/70 p-4', className)}>
      <Skeleton className="h-4 w-2/5" />
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton className={cn('h-3', index === lines - 1 ? 'w-2/3' : 'w-full')} key={index} />
      ))}
    </div>
  )
}

export function PageSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <PanelSkeleton className="p-3" key={index} lines={2} />
        ))}
      </div>
      <PanelSkeleton lines={5} />
      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <PanelSkeleton lines={6} />
        <PanelSkeleton lines={4} />
      </div>
    </div>
  )
}
