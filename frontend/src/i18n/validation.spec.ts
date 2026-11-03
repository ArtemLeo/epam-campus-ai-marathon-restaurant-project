import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { locale, setLocale, supportedLocales, t } from '@/i18n'
import { installNativeValidation } from './validation'

let cleanup: () => void
let form: HTMLFormElement

beforeEach(() => {
  form = document.createElement('form')
  document.body.append(form)
  cleanup = installNativeValidation(t, locale)
})
afterEach(() => { cleanup(); form.remove() })

describe('localized native validation', () => {
  it.each(supportedLocales)('shows a %s error and permits submission after correcting the field', language => {
    setLocale(language)
    form.innerHTML = '<input name="name" required>'
    const field = form.querySelector('input')!
    let prevented = false
    field.addEventListener('invalid', event => { prevented = event.defaultPrevented })
    expect(form.checkValidity()).toBe(false)
    expect(field.validationMessage).toBe(t('validation.required'))
    expect(field.validity.customError).toBe(true)
    expect(prevented).toBe(false)
    field.value = 'Valid name'
    field.dispatchEvent(new Event('input', { bubbles: true }))
    expect(field.validity.customError).toBe(false)
    expect(form.checkValidity()).toBe(true)
  })

  it('retranslates only previously invalid fields, without changing untouched fields', () => {
    form.innerHTML = '<input id="shown" required><input id="untouched" required>'
    const shown = form.querySelector<HTMLInputElement>('#shown')!
    const untouched = form.querySelector<HTMLInputElement>('#untouched')!
    shown.checkValidity()
    setLocale('uk')
    expect(shown.validationMessage).toBe('Заповніть це поле.')
    expect(untouched.validity.customError).toBe(false)
    setLocale('fr')
    expect(shown.validationMessage).toBe('Veuillez remplir ce champ.')
    // A programmatic value update is also re-evaluated when the locale changes.
    shown.value = 'Fixed'
    setLocale('de')
    expect(shown.validity.customError).toBe(false)
    expect(shown.validity.valid).toBe(true)
  })

  it('preserves errors owned by another validator, including errors replacing ours', () => {
    form.innerHTML = '<input required>'
    const field = form.querySelector('input')!
    field.setCustomValidity('Server rejected this value')
    field.checkValidity()
    setLocale('uk')
    field.dispatchEvent(new Event('input', { bubbles: true }))
    expect(field.validationMessage).toBe('Server rejected this value')
    field.setCustomValidity('')
    field.checkValidity()
    expect(field.validationMessage).toBe(t('validation.required'))
    field.setCustomValidity('Another validator changed the error')
    setLocale('es')
    field.dispatchEvent(new Event('change', { bubbles: true }))
    expect(field.validationMessage).toBe('Another validator changed the error')
  })

  it('clears the entire radio group when a different option satisfies the requirement', () => {
    form.innerHTML = '<input type="radio" name="choice" value="a" required><input type="radio" name="choice" value="b">'
    const fields = form.querySelectorAll('input')
    expect(form.checkValidity()).toBe(false)
    fields[1]!.checked = true
    fields[1]!.dispatchEvent(new Event('change', { bubbles: true }))
    expect(fields[0]!.validity.customError).toBe(false)
    expect(form.checkValidity()).toBe(true)
  })

  it('supports select and textarea fields and releases its errors on reset', () => {
    form.innerHTML = '<select required><option value="">Choose</option><option value="a">A</option></select><textarea required></textarea>'
    const select = form.querySelector('select')!
    const textarea = form.querySelector('textarea')!
    expect(form.checkValidity()).toBe(false)
    expect(select.validationMessage).toBe(t('validation.selectRequired'))
    expect(textarea.validationMessage).toBe(t('validation.required'))
    select.value = 'a'
    select.dispatchEvent(new Event('change', { bubbles: true }))
    textarea.value = 'Filled in'
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
    expect(form.checkValidity()).toBe(true)
    textarea.value = ''
    textarea.checkValidity()
    form.reset()
    expect(textarea.validity.customError).toBe(false)
    expect(textarea.validity.valueMissing).toBe(true)
  })

  it.each([
    ['type="email"', 'not-an-email', 'email'],
    ['type="url"', 'not-a-url', 'url'],
    ['type="number" min="2"', '1', 'rangeUnderflow'],
    ['type="number" max="8"', '9', 'rangeOverflow'],
    ['type="number" min="2" step="2"', '3', 'step'],
    ['pattern="[A-Z]{3}"', 'ab', 'pattern'],
  ])('uses the native validity reason for %s', (attributes, value, key) => {
    setLocale('uk')
    form.innerHTML = `<input ${attributes}>`
    const field = form.querySelector('input')!
    field.value = value
    expect(field.checkValidity()).toBe(false)
    expect(field.validationMessage).toBe(t(`validation.${key}`, { min: '2', max: '8' }))
  })

  it('removes listeners and only clears its own messages when disposed', () => {
    form.innerHTML = '<input required><input id="server">'
    const field = form.querySelector('input')!
    const server = form.querySelector<HTMLInputElement>('#server')!
    server.setCustomValidity('Server validation')
    field.checkValidity()
    cleanup()
    expect(field.validity.customError).toBe(false)
    field.checkValidity()
    expect(field.validity.customError).toBe(false)
    expect(server.validationMessage).toBe('Server validation')
  })
})
