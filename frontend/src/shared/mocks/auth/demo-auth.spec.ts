// Port of src/app/shared/mocks/auth/demo-auth.spec.ts (JwtHelperService → jwt-decode + the app's own token check).
import { describe, expect, it, vi } from 'vitest'
import { jwtDecode } from 'jwt-decode'
import { isTokenValid, roleFromToken } from '@/auth/auth-storage'
import { applyDemoLoginFromUrl, createDemoTokens, DEMO_USER, isDemoAuthorization } from './demo-auth'

describe('demo auth (dev-only)', () => {
  it('creates a token the app accepts: decodable, not expired, with the Customer role', () => {
    const { idToken, accessToken } = createDemoTokens()
    expect(accessToken).toBe(idToken)
    expect(isTokenValid(idToken)).toBe(true)
    expect(jwtDecode<Record<string, unknown>>(idToken)['cognito:groups']).toEqual([DEMO_USER.role])
    expect(roleFromToken(idToken)).toBe('Customer')
  })

  it('recognises only demo tokens', () => {
    expect(isDemoAuthorization('Bearer ' + createDemoTokens().idToken)).toBe(true)
    expect(isDemoAuthorization('Bearer real.jwt.token')).toBe(false)
    expect(isDemoAuthorization(null)).toBe(false)
  })

  it('logs in from ?demo and removes the parameter from the address', () => {
    const storage = { setItem: vi.fn() }
    const history = { replaceState: vi.fn(), state: undefined }
    const applied = applyDemoLoginFromUrl(
      { href: 'http://localhost:4200/reservations/demo-reservation/group-order?demo' },
      storage,
      history,
    )

    expect(applied).toBe(true)
    expect(storage.setItem).toHaveBeenCalledWith('user', JSON.stringify(DEMO_USER))
    expect(history.replaceState).toHaveBeenCalledWith(undefined, '', '/reservations/demo-reservation/group-order')
  })

  it('does nothing without ?demo', () => {
    const storage = { setItem: vi.fn() }
    const history = { replaceState: vi.fn(), state: undefined }
    expect(applyDemoLoginFromUrl({ href: 'http://localhost:4200/main' }, storage, history)).toBe(false)
    expect(storage.setItem).not.toHaveBeenCalled()
  })
})
