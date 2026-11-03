import type { Tokens } from '@/models/auth/tokens.model'
import type { UserModel } from '@/models/auth/user.model'
import { AUTH_STORAGE_KEY, USER_STORAGE_KEY } from '@/auth/auth-storage'
import { Roles } from '@/shared/constants/roles'

/**
 * DEV-ONLY mock login for the group-order demonstration.
 * Open any page with `?demo` and you are signed in as the Owner of the demo reservation —
 * no registration, login or backend needed. Sign out with the Logout button in the header.
 * To use the real backend, sign out of the demo and log in with a real account.
 */
export const DEMO_LOGIN_PARAM = 'demo'
export const DEMO_ISSUER = 'green-and-tasty-demo'

export const DEMO_USER: UserModel = {
  id: 'demo-owner',
  firstName: 'Yevhenii',
  lastName: 'Demo',
  email: 'owner@demo.test',
  role: Roles.CUSTOMER,
}

const base64Url = (value: object): string =>
  btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(value))))
    .replace(/=+$/, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')

/** Unsigned JWT: the frontend only decodes tokens (exp, roles); the backend is the one that verifies them. */
export function createDemoTokens(now = Date.now()): Tokens {
  const iat = Math.floor(now / 1000)
  const payload = {
    iss: DEMO_ISSUER,
    sub: DEMO_USER.id,
    email: DEMO_USER.email,
    given_name: DEMO_USER.firstName,
    family_name: DEMO_USER.lastName,
    'cognito:groups': [DEMO_USER.role],
    iat,
    exp: iat + 30 * 24 * 60 * 60,
  }
  const token = `${base64Url({ alg: 'none', typ: 'JWT' })}.${base64Url(payload)}.demo`
  return { idToken: token, accessToken: token }
}

/** True when the request carries the demo token (the mock backend sees it after the API client adds it). */
export function isDemoAuthorization(header: string | null | undefined): boolean {
  if (!header?.startsWith('Bearer ')) return false
  try {
    const encoded = header.slice(7).split('.')[1] ?? ''
    const payload = JSON.parse(atob(encoded.replace(/-/g, '+').replace(/_/g, '/'))) as { iss?: string }
    return payload.iss === DEMO_ISSUER
  } catch {
    return false
  }
}

/**
 * Called once on startup (dev only). With `?demo` in the URL it stores the demo tokens and user
 * in localStorage and removes the parameter from the address.
 */
export function applyDemoLoginFromUrl(
  location: Pick<Location, 'href'> = window.location,
  storage: Pick<Storage, 'setItem'> = localStorage,
  history: Pick<History, 'replaceState' | 'state'> = window.history,
): boolean {
  const url = new URL(location.href)
  if (!url.searchParams.has(DEMO_LOGIN_PARAM)) return false

  storage.setItem(AUTH_STORAGE_KEY, JSON.stringify(createDemoTokens()))
  storage.setItem(USER_STORAGE_KEY, JSON.stringify(DEMO_USER))

  url.searchParams.delete(DEMO_LOGIN_PARAM)
  history.replaceState(history.state, '', url.pathname + url.search + url.hash)
  return true
}
