import * as React from 'react'

import { cn } from '@/lib/utils'

export type CheckboxCheckedState = boolean | 'indeterminate'

export interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type' | 'checked' | 'defaultChecked'> {
  checked?: CheckboxCheckedState
  defaultChecked?: CheckboxCheckedState
  onCheckedChange?: (checked: boolean) => void
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, checked, defaultChecked, onCheckedChange, onChange, ...props }, ref) => {
    const inputRef = React.useRef<HTMLInputElement | null>(null)
    const isControlled = checked !== undefined
    const [uncontrolledState, setUncontrolledState] = React.useState<CheckboxCheckedState>(defaultChecked ?? false)
    const currentState = isControlled ? checked : uncontrolledState
    const isIndeterminate = currentState === 'indeterminate'
    const isChecked = currentState === true

    React.useEffect(() => {
      if (inputRef.current) {
        inputRef.current.indeterminate = isIndeterminate
      }
    }, [isIndeterminate])

    return (
      <input
        aria-checked={isIndeterminate ? 'mixed' : isChecked === true ? 'true' : 'false'}
        checked={isChecked}
        className={cn(
          'peer h-6 w-6 shrink-0 rounded-[4px] border border-input bg-background',
          'accent-[hsl(var(--primary))] shadow-sm transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'data-[state=checked]:border-primary data-[state=checked]:bg-primary/10',
          'data-[state=indeterminate]:border-primary data-[state=indeterminate]:bg-primary/10',
          className,
        )}
        data-state={isIndeterminate ? 'indeterminate' : isChecked === true ? 'checked' : 'unchecked'}
        onChange={(event) => {
          if (!isControlled) {
            setUncontrolledState(event.target.checked)
          }
          onChange?.(event)
          onCheckedChange?.(event.target.checked)
        }}
        ref={(node) => {
          inputRef.current = node
          if (typeof ref === 'function') {
            ref(node)
          } else if (ref) {
            ;(ref as React.MutableRefObject<HTMLInputElement | null>).current = node
          }
        }}
        type="checkbox"
        {...props}
      />
    )
  },
)

Checkbox.displayName = 'Checkbox'
