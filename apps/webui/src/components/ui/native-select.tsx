import type { SelectHTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

export function NativeSelect({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        'flex h-11 w-full items-center justify-between rounded-lg border border-input bg-card/85 px-3.5 py-2 text-sm text-foreground shadow-[0_1px_0_hsl(0_0%_100%/0.62)_inset] ring-offset-background',
        'focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-ring/45 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  )
}
