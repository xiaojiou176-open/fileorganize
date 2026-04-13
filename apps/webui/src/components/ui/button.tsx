import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap rounded-lg border border-transparent text-sm font-medium tracking-[-0.01em] transition-[background-color,border-color,color,box-shadow,transform] duration-200 disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background active:translate-y-[1px]',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground shadow-[0_1px_0_hsl(0_0%_100%/0.28)_inset,0_12px_28px_-18px_hsl(var(--primary)/0.75)] hover:bg-primary/95',
        secondary: 'border-border/70 bg-secondary/80 text-secondary-foreground shadow-[0_1px_0_hsl(0_0%_100%/0.65)_inset] hover:bg-secondary',
        outline: 'border-border bg-card/75 text-foreground hover:border-primary/25 hover:bg-accent/80',
        ghost: 'text-muted-foreground hover:border-border/70 hover:bg-card/70 hover:text-foreground',
        destructive: 'bg-destructive text-destructive-foreground shadow-[0_1px_0_hsl(0_0%_100%/0.18)_inset,0_12px_28px_-18px_hsl(var(--destructive)/0.55)] hover:bg-destructive/92',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 px-3',
        lg: 'h-11 px-5 text-[0.95rem]',
        icon: 'h-10 w-10 rounded-full',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    const buttonProps = asChild
      ? props
      : ({
          type: 'button' as const,
          ...props,
        } satisfies React.ButtonHTMLAttributes<HTMLButtonElement>)
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...buttonProps} />
  },
)
Button.displayName = 'Button'

export { Button }
