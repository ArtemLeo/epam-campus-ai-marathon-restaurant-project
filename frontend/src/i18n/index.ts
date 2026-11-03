import { computed, watch } from 'vue'
import { createI18n } from 'vue-i18n'
import { validationMessages } from './validation'
import { errorMessages } from './errors'
import { coreMessages } from './core'
import { customerMessages } from './customer'
import { staffMessages } from './staff'
import { orderMessages } from './orders'

export const supportedLocales = ['en', 'uk', 'fr', 'es', 'de'] as const
export type Locale = typeof supportedLocales[number]
export const languageNames: Record<Locale, string> = { en: 'English', uk: 'Українська', fr: 'Français', es: 'Español', de: 'Deutsch' }
const tags: Record<Locale, string> = { en: 'en-US', uk: 'uk-UA', fr: 'fr-FR', es: 'es-ES', de: 'de-DE' }
export const LOCALE_STORAGE_KEY = 'restaurant.locale'

export function matchLocale(value: string | null | undefined): Locale | null {
  const short = value?.toLowerCase().split(/[-_]/)[0]
  return supportedLocales.includes(short as Locale) ? short as Locale : null
}

export function preferredLocale(): Locale {
  try {
    const saved = matchLocale(localStorage.getItem(LOCALE_STORAGE_KEY))
    if (saved) return saved
  } catch { /* Preferences are optional in private/restricted browsers. */ }
  if (typeof navigator !== 'undefined') {
    for (const language of navigator.languages ?? [navigator.language]) {
      const supported = matchLocale(language)
      if (supported) return supported
    }
  }
  return 'en'
}

export const messages = Object.fromEntries(supportedLocales.map(code => [code, {
  ...validationMessages[code], ...errorMessages[code], ...coreMessages[code], ...customerMessages[code], ...staffMessages[code], ...orderMessages[code],
}]))

export const i18n = createI18n({
  legacy: false,
  locale: preferredLocale(),
  fallbackLocale: 'en',
  messages,
  pluralRules: {
    uk: (count: number, length: number) => {
      if (length < 3) return count === 1 ? 0 : 1
      const n = Math.abs(count)
      if (!Number.isInteger(n)) return 2
      if (n % 10 === 1 && n % 100 !== 11) return 0
      if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14)) return 1
      return 2
    },
  },
})
export const locale = i18n.global.locale
export const localeTag = computed(() => tags[locale.value as Locale] ?? tags.en)
export function t(key: string, params: Record<string, string | number> = {}, plural?: number): string {
  return i18n.global.t(key, params, plural === undefined ? {} : { plural })
}
export function setLocale(value: string): void {
  const supported = matchLocale(value)
  if (!supported) return
  locale.value = supported
  try { localStorage.setItem(LOCALE_STORAGE_KEY, supported) } catch { /* The current tab still switches. */ }
}
watch(locale, value => {
  if (typeof document !== 'undefined') document.documentElement.lang = value
}, { immediate: true, flush: 'sync' })

export function roleLabel(role: string | null | undefined): string {
  return role && ['Admin', 'Customer', 'Waiter'].includes(role) ? t(`core.role${role}`) : ''
}
