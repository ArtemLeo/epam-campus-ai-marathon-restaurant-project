import { localeTag } from '@/i18n'
import { RESTAURANT_TIMEZONE } from './date-time'
type DateInput = string | Date | null | undefined

function toDate(value: DateInput): Date | null {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

/** "27 Oct 2026, 14:30" (or with custom Intl options). */
export function formatDate(value: DateInput, options: Intl.DateTimeFormatOptions = {}): string {
  const date = toDate(value)
  if (!date) return '—'
  const defaults: Intl.DateTimeFormatOptions = {
    timeZone: RESTAURANT_TIMEZONE,
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }
  return date.toLocaleDateString(localeTag.value, { ...defaults, ...options })
}

/** "Oct 21, 2026" — Angular `date: 'mediumDate'`. */
export function formatMediumDate(value: DateInput): string {
  const date = toDate(value)
  return date ? date.toLocaleDateString(localeTag.value, { timeZone: RESTAURANT_TIMEZONE, month: 'short', day: 'numeric', year: 'numeric' }) : '—'
}

/** "16:00" (24-hour clock, like the designs). */
export function formatTime(value: DateInput): string {
  const date = toDate(value)
  return date ? date.toLocaleTimeString(localeTag.value, { timeZone: RESTAURANT_TIMEZONE, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }) : '—'
}

/** "14:05:30" */
export function formatClock(value: DateInput): string {
  const date = toDate(value)
  return date ? date.toLocaleTimeString(localeTag.value, { timeZone: RESTAURANT_TIMEZONE, hour: '2-digit', minute: '2-digit', hourCycle: 'h23', second: '2-digit' }) : '—'
}

/** "$440.00" — Angular `currency` pipe defaults (USD, two decimals). */
export function formatCurrency(amount: number | null | undefined, currency = 'USD'): string {
  if (amount == null) return '—'
  return new Intl.NumberFormat(localeTag.value, { style: 'currency', currency }).format(amount)
}

export function formatNumber(value: number | null | undefined, options: Intl.NumberFormatOptions = {}): string {
  return value == null ? '—' : new Intl.NumberFormat(localeTag.value, options).format(value)
}

/** Values are percentages (0–100), not fractions. */
export function formatPercent(value: number): string {
  return new Intl.NumberFormat(localeTag.value, { style: 'percent', maximumFractionDigits: 1 }).format(value / 100)
}
