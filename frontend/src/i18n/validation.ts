import { watch, type Ref } from 'vue'

const entries = {
  required: ['Please fill in this field.', 'Заповніть це поле.', 'Veuillez remplir ce champ.', 'Completa este campo.', 'Bitte füllen Sie dieses Feld aus.'],
  selectRequired: ['Please select an option.', 'Виберіть один із варіантів.', 'Veuillez sélectionner une option.', 'Selecciona una opción.', 'Bitte wählen Sie eine Option aus.'],
  checkboxRequired: ['Please tick this box to continue.', 'Поставте позначку, щоб продовжити.', 'Veuillez cocher cette case pour continuer.', 'Marca esta casilla para continuar.', 'Bitte aktivieren Sie dieses Kontrollkästchen, um fortzufahren.'],
  email: ['Enter a valid email address.', 'Введіть коректну електронну адресу.', 'Saisissez une adresse e-mail valide.', 'Introduce una dirección de correo válida.', 'Geben Sie eine gültige E-Mail-Adresse ein.'],
  url: ['Enter a valid web address.', 'Введіть коректну вебадресу.', 'Saisissez une adresse web valide.', 'Introduce una dirección web válida.', 'Geben Sie eine gültige Webadresse ein.'],
  tooShort: ['Minimum number of characters: {min}.', 'Мінімальна кількість символів: {min}.', 'Nombre minimal de caractères : {min}.', 'Número mínimo de caracteres: {min}.', 'Mindestanzahl an Zeichen: {min}.'],
  tooLong: ['Maximum number of characters: {max}.', 'Максимальна кількість символів: {max}.', 'Nombre maximal de caractères : {max}.', 'Número máximo de caracteres: {max}.', 'Maximale Anzahl an Zeichen: {max}.'],
  rangeUnderflow: ['Enter a value greater than or equal to {min}.', 'Введіть значення не менше ніж {min}.', 'Saisissez une valeur supérieure ou égale à {min}.', 'Introduce un valor mayor o igual que {min}.', 'Geben Sie einen Wert größer oder gleich {min} ein.'],
  rangeOverflow: ['Enter a value less than or equal to {max}.', 'Введіть значення не більше ніж {max}.', 'Saisissez une valeur inférieure ou égale à {max}.', 'Introduce un valor menor o igual que {max}.', 'Geben Sie einen Wert kleiner oder gleich {max} ein.'],
  badNumber: ['Enter a valid number.', 'Введіть коректне число.', 'Saisissez un nombre valide.', 'Introduce un número válido.', 'Geben Sie eine gültige Zahl ein.'],
  pattern: ['Use the required format for this field.', 'Використайте потрібний формат цього поля.', 'Respectez le format demandé pour ce champ.', 'Usa el formato requerido para este campo.', 'Verwenden Sie das für dieses Feld erforderliche Format.'],
  step: ['Choose a value that matches the required increment.', 'Виберіть значення з урахуванням допустимого кроку.', 'Choisissez une valeur respectant l’incrément demandé.', 'Elige un valor que respete el incremento requerido.', 'Wählen Sie einen Wert, der der vorgegebenen Schrittweite entspricht.'],
  invalid: ['Check the value entered in this field.', 'Перевірте значення в цьому полі.', 'Vérifiez la valeur saisie dans ce champ.', 'Comprueba el valor introducido en este campo.', 'Überprüfen Sie den eingegebenen Wert in diesem Feld.'],
} satisfies Record<string, [string, string, string, string, string]>

function messages(index: 0 | 1 | 2 | 3 | 4) {
  return { validation: Object.fromEntries(Object.entries(entries).map(([key, translations]) => [key, translations[index]])) }
}
export const validationMessages = { en: messages(0), uk: messages(1), fr: messages(2), es: messages(3), de: messages(4) }

type Field = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
type Translate = (key: string, params?: Record<string, string | number>) => string

function isField(target: EventTarget | null): target is Field {
  return target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement
}

function bound(value: string, field: HTMLInputElement, locale: string): string {
  if (field.type === 'number' || field.type === 'range') {
    const number = Number(value)
    if (Number.isFinite(number)) return new Intl.NumberFormat(locale).format(number)
  }
  if (field.type === 'date' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const date = new Date(`${value}T12:00:00Z`)
    if (!Number.isNaN(date.getTime())) return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeZone: 'UTC' }).format(date)
  }
  return value
}

function message(field: Field, translate: Translate, locale: string): string {
  const validity = field.validity
  if (validity.badInput) return translate(field instanceof HTMLInputElement && field.type === 'number' ? 'validation.badNumber' : 'validation.invalid')
  if (validity.valueMissing) {
    if (field instanceof HTMLSelectElement || (field instanceof HTMLInputElement && field.type === 'radio')) return translate('validation.selectRequired')
    if (field instanceof HTMLInputElement && field.type === 'checkbox') return translate('validation.checkboxRequired')
    return translate('validation.required')
  }
  if (validity.typeMismatch && field instanceof HTMLInputElement) {
    if (field.type === 'email') return translate('validation.email')
    if (field.type === 'url') return translate('validation.url')
  }
  if (field instanceof HTMLInputElement) {
    if (validity.rangeUnderflow) return translate('validation.rangeUnderflow', { min: bound(field.min, field, locale) })
    if (validity.rangeOverflow) return translate('validation.rangeOverflow', { max: bound(field.max, field, locale) })
  }
  if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) {
    if (validity.tooShort) return translate('validation.tooShort', { min: field.minLength })
    if (validity.tooLong) return translate('validation.tooLong', { max: field.maxLength })
  }
  if (validity.patternMismatch) return translate('validation.pattern')
  if (validity.stepMismatch) return translate('validation.step')
  return translate('validation.invalid')
}

/** Translate native validation bubbles while keeping the browser's validation and focus behavior. */
export function installNativeValidation(translate: Translate, currentLocale: Ref<string>, scope: Document = document): () => void {
  // Only errors created here may be cleared or retranslated; server/custom validators retain ownership.
  const managed = new Map<Field, string>()

  function clear(field: Field): void {
    if (managed.get(field) === field.validationMessage) field.setCustomValidity('')
    managed.delete(field)
  }

  function localize(field: Field): void {
    if (!field.willValidate) return
    if (field.validity.customError) {
      if (managed.get(field) !== field.validationMessage) {
        managed.delete(field)
        return
      }
      clear(field)
    }
    if (field.validity.valid) return
    const text = message(field, translate, currentLocale.value)
    field.setCustomValidity(text)
    managed.set(field, text)
  }

  function onInvalid(event: Event): void {
    if (isField(event.target)) localize(event.target)
    // Do not preventDefault: native form blocking, focus and the bubble stay enabled.
  }

  function onEdit(event: Event): void {
    const field = event.target
    if (!isField(field)) return
    clear(field)
    if (field instanceof HTMLInputElement && field.type === 'radio' && field.name) {
      for (const other of [...managed.keys()]) {
        if (other instanceof HTMLInputElement && other.type === 'radio' && other.name === field.name && other.form === field.form) clear(other)
      }
    }
  }

  function onReset(event: Event): void {
    if (!(event.target instanceof HTMLFormElement)) return
    for (const field of [...managed.keys()]) if (field.form === event.target) clear(field)
  }

  scope.addEventListener('invalid', onInvalid, true)
  scope.addEventListener('input', onEdit, true)
  scope.addEventListener('change', onEdit, true)
  scope.addEventListener('reset', onReset, true)
  const stop = watch(currentLocale, () => {
    for (const field of [...managed.keys()]) {
      if (field.isConnected) localize(field)
      else clear(field)
    }
  }, { flush: 'sync' })

  return () => {
    stop()
    scope.removeEventListener('invalid', onInvalid, true)
    scope.removeEventListener('input', onEdit, true)
    scope.removeEventListener('change', onEdit, true)
    scope.removeEventListener('reset', onReset, true)
    for (const field of [...managed.keys()]) clear(field)
  }
}
