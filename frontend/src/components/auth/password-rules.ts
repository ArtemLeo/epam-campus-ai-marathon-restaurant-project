/** Form rules shared by sign-in, registration and the profile (Angular FormValidatorsService). */
import { t } from '@/i18n'

export const EMAIL_PATTERN = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/
/** Unicode names, including Ukrainian letters; matches the backend validator. */
export const NAME_PATTERN = /^[\p{L}\p{M}]+(?:[ '\u2019-][\p{L}\p{M}]+)*$/u
export const NAME_MAX_LENGTH = 50
export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 16

const SPECIAL_CHARACTER = /[!@#$%^&*()_+{}[\]:;<>,.?~\\/-]/

export interface PasswordValidity {
  hasUppercase: boolean
  hasLowercase: boolean
  hasNumber: boolean
  hasSpecialCharacter: boolean
  lengthValid: boolean
}

export interface PasswordStrength {
  valid: PasswordValidity
  /** "Strong" once at least four of the five rules pass. */
  strength: 'Strong' | 'Weak'
}

export function evaluatePasswordStrength(password: string): PasswordStrength {
  const valid: PasswordValidity = {
    hasUppercase: /[A-Z]/.test(password),
    hasLowercase: /[a-z]/.test(password),
    hasNumber: /[0-9]/.test(password),
    hasSpecialCharacter: SPECIAL_CHARACTER.test(password),
    lengthValid: password.length >= PASSWORD_MIN_LENGTH && password.length <= PASSWORD_MAX_LENGTH,
  }
  const passed = Object.values(valid).filter(Boolean).length
  return { valid, strength: passed >= 4 ? 'Strong' : 'Weak' }
}

/** Cognito's password policy needs every rule, so the form only submits a fully valid password. */
export function isPasswordAcceptable(password: string): boolean {
  return Object.values(evaluatePasswordStrength(password).valid).every(Boolean)
}

/** The rule list shown under the password field, in the Angular order and wording. */
export const PASSWORD_RULES: { key: keyof PasswordValidity; text: string }[] = [
  { key: 'hasUppercase', text: 'At least one uppercase letter required' },
  { key: 'hasLowercase', text: 'At least one lowercase letter required' },
  { key: 'hasNumber', text: 'At least one number required' },
  { key: 'hasSpecialCharacter', text: 'At least one special character @ required' },
  { key: 'lengthValid', text: 'Password must be 8–16 characters long' },
]

/** Error for a first/last name field, or '' when the value is acceptable (the API needs 2–50 characters). */
export function nameError(value: string, field: 'First name' | 'Last name'): string {
  const prefix = field === 'First name' ? 'first' : 'last'
  if (!value) return t(`core.${prefix}Required`)
  if (value.length > NAME_MAX_LENGTH) return t(`core.${prefix}Long`)
  if (!NAME_PATTERN.test(value)) return t('core.nameCharacters')
  if (value.length < 2) return t(`core.${prefix}Short`)
  return ''
}
