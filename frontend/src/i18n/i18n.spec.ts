import { describe, expect, it, vi } from 'vitest'
import { messages, supportedLocales, setLocale, preferredLocale, matchLocale, LOCALE_STORAGE_KEY, t, locale } from './index'
import { localizedDish, localizedLocation, localizedMeasure } from './catalog'
import { translateApiMessage } from './errors'
import { notificationMessage } from './notifications'
import { formatCurrency, formatNumber, formatTime } from '@/utils/formatters'

function flatten(value: Record<string, unknown>, prefix = ''): Record<string, string> {
  return Object.fromEntries(Object.entries(value).flatMap(([key, item]) => typeof item === 'string'
    ? [[`${prefix}${key}`, item]] : Object.entries(flatten(item as Record<string, unknown>, `${prefix}${key}.`))))
}
const placeholders = (text: string) => [...new Set([...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]))].sort()

describe('five-language contract', () => {
  it.each(supportedLocales)('%s has every message and placeholder, and all messages compile', code => {
    const source = flatten(messages.en!)
    const target = flatten(messages[code]!)
    expect(Object.keys(target).sort()).toEqual(Object.keys(source).sort())
    setLocale(code)
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    for (const [key, value] of Object.entries(target)) {
      expect(value.trim(), key).not.toBe('')
      expect(placeholders(value), `${code}.${key}`).toEqual(placeholders(source[key]!))
      const params = Object.fromEntries(placeholders(value).map(name => [name, name === 'count' ? 2 : 'example']))
      expect(t(key, params, value.includes('|') ? 2 : undefined), key).not.toBe(key)
    }
    expect(warn.mock.calls).toEqual([])
    expect(error.mock.calls).toEqual([])
  })

  it('prefers a saved choice, then a supported browser language, then English', () => {
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['pt-BR', 'fr-CA'])
    expect(preferredLocale()).toBe('fr')
    localStorage.setItem(LOCALE_STORAGE_KEY, 'de')
    expect(preferredLocale()).toBe('de')
    localStorage.setItem(LOCALE_STORAGE_KEY, 'unsupported')
    expect(preferredLocale()).toBe('fr')
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['ja-JP'])
    expect(preferredLocale()).toBe('en')
    expect(matchLocale('UK-ua')).toBe('uk')
    expect(matchLocale('ru')).toBeNull()
  })

  it('switches the page language and works when browser storage is disabled', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Storage disabled') })
    setLocale('uk')
    expect(locale.value).toBe('uk')
    expect(document.documentElement.lang).toBe('uk')
    setLocale('invalid')
    expect(locale.value).toBe('uk')
  })

  it('formats money and numbers without changing currency or restaurant wall time', () => {
    for (const code of supportedLocales) {
      setLocale(code)
      expect(formatTime('2027-04-01T10:30:00Z')).toBe('14:30')
    }
    setLocale('en')
    expect(formatCurrency(12.5)).toBe('$12.50')
    setLocale('de')
    expect(formatCurrency(12.5)).toContain('12,50')
    expect(formatCurrency(12.5)).toContain('$')
    expect(formatNumber(1234.5)).toBe('1.234,5')
    expect(localizedMeasure('12.5 g')).toBe('12,5 g')
    setLocale('uk')
    expect(localizedMeasure('350 kcal')).toBe('350 ккал')
    expect(localizedMeasure('A custom portion')).toBe('A custom portion')
  })

  it('uses curated demo translations and preserves custom source data and explicit translations', () => {
    const seed = { id: 'd1', name: 'Spring Salad', description: 'Young greens, radish, cucumber and herb dressing.' }
    setLocale('uk')
    expect(localizedDish(seed)).toMatchObject({ id: 'd1', name: 'Весняний салат', description: 'Молода зелень, редиска, огірок і заправка з травами.' })
    expect(seed.name).toBe('Spring Salad')
    expect(localizedDish({ ...seed, description: 'An administrator changed the recipe' }).description).toBe('An administrator changed the recipe')
    expect(localizedDish({ ...seed, translations: { uk: { name: 'Авторська назва' } } }).name).toBe('Авторська назва')
    expect(localizedDish({ name: 'Custom dish' }).name).toBe('Custom dish')
    expect(localizedLocation({ address: 'Original street', description: 'Original text', translations: { uk: { description: 'Опис ресторану' } } })).toMatchObject({ address: 'Original street', description: 'Опис ресторану' })
  })

  it('translates server reasons and structured notifications without translating user content', () => {
    setLocale('uk')
    expect(translateApiMessage('Pre-orders can only be modified up to 30 minutes before the reservation start time (13:00).')).toContain('30 хвилин')
    expect(translateApiMessage('Table is busy', 409)).toContain('столик')
    expect(translateApiMessage('Future unrecognised backend error', 500)).toContain('Помилка сервера')
    const text = notificationMessage({ id: 'n', orderId: 'o', reservationId: 'r', createdAt: '2027-04-01T10:30:00Z', message: 'Legacy English message', isRead: false, kind: 'NewOrder', tableNumber: 2, guestCount: 3, locationAddress: 'Rustaveli Avenue, 48', startTime: '2027-04-01T10:30:00Z', dishes: [{ id: 'd', name: 'Spring Salad', quantity: 2 }] })
    expect(text).toContain('Нове попереднє замовлення')
    expect(text).toContain('Rustaveli Avenue, 48')
    expect(text).toContain('Весняний салат')
  })
})
