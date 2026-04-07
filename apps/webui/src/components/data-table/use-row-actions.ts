import { useCallback, useMemo, useState } from 'react'

export function useRowActions() {
  const [busyByKey, setBusyByKey] = useState<Record<string, boolean>>({})

  const runAction = useCallback(async (key: string, action: () => Promise<void>): Promise<boolean> => {
    if (busyByKey[key]) {
      return false
    }

    setBusyByKey((prev) => ({
      ...prev,
      [key]: true,
    }))

    try {
      await action()
      return true
    } catch {
      return false
    } finally {
      setBusyByKey((prev) => {
        const next = { ...prev }
        delete next[key]
        return next
      })
    }
  }, [busyByKey])

  const hasBusy = useMemo(() => Object.keys(busyByKey).length > 0, [busyByKey])

  return {
    runAction,
    hasBusy,
    isBusy: (key: string) => Boolean(busyByKey[key]),
  }
}
