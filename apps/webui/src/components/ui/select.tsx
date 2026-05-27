import * as React from 'react'
import * as SelectPrimitive from '@radix-ui/react-select'
import { Check, ChevronDown, ChevronUp } from 'lucide-react'

import { useI18n } from '@/lib/i18n'
import { cn } from '@/lib/utils'

export const SelectRoot = SelectPrimitive.Root
export const SelectGroup = SelectPrimitive.Group
export const SelectValue = SelectPrimitive.Value

export interface SelectProps {
  children: React.ReactNode
  className?: string
  id?: string
  value?: string
  defaultValue?: string
  name?: string
  placeholder?: string
  disabled?: boolean
  onValueChange?: (value: string) => void
  onChange?: (event: { target: { value: string } }) => void
}

function asOptions(children: React.ReactNode): Array<{ value: string; label: React.ReactNode; disabled?: boolean }> {
  return React.Children.toArray(children).flatMap((child) => {
    if (!React.isValidElement<{ value?: string; disabled?: boolean; children?: React.ReactNode }>(child)) {
      return []
    }
    if (child.type !== 'option') {
      return []
    }
    const rawValue = child.props.value ?? child.props.children
    return [
      {
        value: String(rawValue ?? ''),
        label: child.props.children,
        disabled: Boolean(child.props.disabled),
      },
    ]
  })
}

export function Select({
  children,
  className,
  id,
  value,
  defaultValue,
  name,
  placeholder,
  disabled,
  onChange,
  onValueChange,
}: SelectProps) {
  const { t } = useI18n()
  const options = React.useMemo(() => asOptions(children), [children])
  const isControlled = value !== undefined
  const [internalValue, setInternalValue] = React.useState(defaultValue ?? '')
  const resolvedPlaceholder = placeholder ?? t('select.placeholder')

  React.useEffect(() => {
    if (!isControlled && defaultValue !== undefined) {
      setInternalValue(defaultValue)
    }
  }, [defaultValue, isControlled])

  const rawValue = isControlled ? (value ?? '') : internalValue
  const hasSelected = options.some((item) => item.value === rawValue)
  const syncedValue = hasSelected ? rawValue : ''

  return (
    <SelectPrimitive.Root
      disabled={disabled}
      onValueChange={(nextValue) => {
        if (!isControlled) {
          setInternalValue(nextValue)
        }
        onValueChange?.(nextValue)
        onChange?.({ target: { value: nextValue } })
      }}
      value={syncedValue}
    >
      <SelectPrimitive.Trigger
        className={cn(
          'flex h-10 w-full items-center justify-between rounded-xl border border-input bg-background px-3 py-2 text-sm ring-offset-background',
          'focus:outline-none focus:ring-2 focus:ring-ring/60 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        id={id}
      >
        <SelectPrimitive.Value placeholder={resolvedPlaceholder}>
          {hasSelected ? options.find((item) => item.value === syncedValue)?.label : undefined}
        </SelectPrimitive.Value>
        <SelectPrimitive.Icon asChild>
          <ChevronDown className="h-4 w-4 opacity-60" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          className={cn(
            'relative z-50 max-h-96 min-w-[8rem] overflow-hidden rounded-xl border border-border bg-popover text-popover-foreground shadow-card',
            'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2',
            'data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
          )}
          position="popper"
        >
          <SelectPrimitive.ScrollUpButton className="flex cursor-default items-center justify-center py-1">
            <ChevronUp className="h-4 w-4" />
          </SelectPrimitive.ScrollUpButton>
          <SelectPrimitive.Viewport className="p-1">
            {options.map((item) => (
              <SelectPrimitive.Item
                className={cn(
                  'relative flex w-full cursor-default select-none items-center rounded-lg py-1.5 pl-8 pr-2 text-sm outline-none',
                  'focus:bg-muted focus:text-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
                )}
                disabled={item.disabled}
                key={item.value}
                value={item.value}
              >
                <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
                  <SelectPrimitive.ItemIndicator>
                    <Check className="h-4 w-4" />
                  </SelectPrimitive.ItemIndicator>
                </span>
                <SelectPrimitive.ItemText>{item.label}</SelectPrimitive.ItemText>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
          <SelectPrimitive.ScrollDownButton className="flex cursor-default items-center justify-center py-1">
            <ChevronDown className="h-4 w-4" />
          </SelectPrimitive.ScrollDownButton>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
      {name ? <input name={name} type="hidden" value={syncedValue} /> : null}
    </SelectPrimitive.Root>
  )
}
