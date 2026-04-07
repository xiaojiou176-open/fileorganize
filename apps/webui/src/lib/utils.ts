import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

import type { Locale } from '@/lib/i18n'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(value?: string, locale: Locale = 'en') {
  if (!value) {
    return '-'
  }
  const date = new Date(value)
  if (Number.isNaN(date.valueOf())) {
    return value
  }
  const documentLocale =
    typeof document !== 'undefined' && document.documentElement.lang === 'zh-CN'
      ? 'zh-CN'
      : locale

  return new Intl.DateTimeFormat(documentLocale === 'zh-CN' ? 'zh-CN' : 'en-US', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function toTitleCase(input: string) {
  return input
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(' ')
}

export function progressToPercent(value: number) {
  if (!Number.isFinite(value)) {
    return 0
  }
  if (value <= 1) {
    return Math.round(value * 100)
  }
  return Math.round(value)
}
