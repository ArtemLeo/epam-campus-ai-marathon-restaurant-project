import { afterEach, beforeEach } from 'vitest'
import { setLocale } from '@/i18n'
import { config } from '@vue/test-utils'
import { clearToasts } from '@/composables/useToast'

// Dates in specs are UTC instants; render them in one zone so assertions do not depend on the machine.
process.env.TZ = 'UTC'

// AppModal teleports to <body>; rendering it in place lets specs query the dialog inside the page.
config.global.stubs = { teleport: true }

beforeEach(() => {
  setLocale('en')
  localStorage.clear()
})

afterEach(() => {
  clearToasts()
})
