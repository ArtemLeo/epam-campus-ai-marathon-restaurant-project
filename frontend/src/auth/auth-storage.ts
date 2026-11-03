import { jwtDecode } from 'jwt-decode'
import type { Tokens } from '@/models/auth/tokens.model'
import type { UserModel } from '@/models/auth/user.model'
import { Roles } from '@/shared/constants/roles'

// Same localStorage keys as the Angular AuthenticationService.
export const AUTH_STORAGE_KEY = 'auth'
export const USER_STORAGE_KEY = 'user'

interface TokenClaims {
  exp?: number
  'cognito:groups'?: string[] | string
}

function decode(token: string): TokenClaims | null {
  try {
    return jwtDecode<TokenClaims>(token)
  } catch {
    return null
  }
}

/** Only an unexpired, decodable token is sent; the server verifies its signature. */
export function isTokenValid(token: string | null | undefined, now: number = Date.now()): boolean {
  if (!token) return false
  const claims = decode(token)
  if (!claims) return false
  return typeof claims.exp === 'number' && claims.exp > Math.floor(now / 1000)
}

export function tokenExpiresAt(token: string): number | null {
  const expiry = decode(token)?.exp
  return typeof expiry === 'number' ? expiry * 1000 : null
}

/** Highest-privilege role from the Cognito `cognito:groups` claim. */
export function roleFromToken(token: string | null | undefined): string | null {
  if (!token) return null
  const groups = decode(token)?.['cognito:groups']
  const list = Array.isArray(groups) ? groups : typeof groups === 'string' ? groups.split(',') : []
  const names = list.map((group) => group.trim())
  for (const role of [Roles.ADMIN, Roles.WAITER, Roles.CUSTOMER]) {
    if (names.includes(role)) return role
  }
  return null
}

function readJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

export function readTokens(): Tokens | null {
  const tokens = readJson<Partial<Tokens>>(AUTH_STORAGE_KEY)
  return tokens?.idToken && tokens.accessToken ? { idToken: tokens.idToken, accessToken: tokens.accessToken } : null
}

/** The idToken to send as `Authorization: Bearer …`, or null when missing or expired. */
export function readIdToken(): string | null {
  const idToken = readTokens()?.idToken ?? null
  return isTokenValid(idToken) ? idToken : null
}

export function readStoredUser(): UserModel | null {
  return readJson<UserModel>(USER_STORAGE_KEY)
}

export function writeTokens(tokens: Tokens): void {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(tokens))
}

export function writeUser(user: UserModel): void {
  localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user))
}

export function clearSession(): void {
  localStorage.removeItem(AUTH_STORAGE_KEY)
  localStorage.removeItem(USER_STORAGE_KEY)
}
