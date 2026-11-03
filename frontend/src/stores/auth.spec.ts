import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, disposePinia, setActivePinia, type Pinia } from 'pinia'
import { useAuthStore } from './auth'
import { useCartStore } from './cart'
import { useNotificationsStore } from './notifications'
import { apiRequest, setMockHandler, setUnauthorizedHandler } from '@/services/http/api-client'
import { useLoginModal, closeLogin } from '@/components/auth/login-modal'
import type { Order } from '@/services/api'

let pinia: Pinia
function signInFor(seconds: number): void {
  const token = `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + seconds, 'cognito:groups': ['Waiter'] }))}.signature`
  localStorage.setItem('auth', JSON.stringify({ idToken: token, accessToken: token }))
  localStorage.setItem('user', JSON.stringify({ id: 'waiter1', firstName: 'Nino', lastName: 'Beridze', email: 'waiter@test.com', role: 'Waiter' }))
}
beforeEach(() => { pinia = createPinia(); setActivePinia(pinia); closeLogin() })
afterEach(() => { disposePinia(pinia); setMockHandler(undefined); setUnauthorizedHandler(undefined); vi.useRealTimers() })

describe('session isolation', () => {
  it('clears private cart and notifications when signing out', () => {
    signInFor(3600)
    const auth = useAuthStore()
    const cart = useCartStore()
    const notifications = useNotificationsStore()
    cart.orders = [{ orderId: 'private' }] as Order[]
    notifications.notifications = [{ id: 'n1', message: 'Private reservation', orderId: null, reservationId: 'r1', createdAt: '', isRead: false }]
    auth.logout()
    expect(cart.orders).toEqual([])
    expect(notifications.notifications).toEqual([])
    expect(localStorage.getItem('auth')).toBeNull()
    expect(auth.isAuthenticated).toBe(false)
  })
  it('expires the UI session without requiring a reload or a request', async () => {
    vi.useFakeTimers()
    signInFor(1)
    const auth = useAuthStore()
    expect(auth.isAuthenticated).toBe(true)
    await vi.advanceTimersByTimeAsync(1100)
    expect(auth.isAuthenticated).toBe(false)
    expect(useLoginModal().open).toBe(true)
  })
  it('clears an authenticated session rejected by the server but keeps it for a rejected guest token', async () => {
    signInFor(3600)
    const auth = useAuthStore()
    setMockHandler(() => Promise.resolve({ status: 401, body: { message: 'Expired' } }))
    await expect(apiRequest('/guest/sessions/s1', { guestToken: 'expired', skipErrorToast: true })).rejects.toThrow()
    expect(auth.isAuthenticated).toBe(true)
    await expect(apiRequest('/me', { skipErrorToast: true })).rejects.toThrow()
    expect(auth.isAuthenticated).toBe(false)
    expect(useLoginModal().open).toBe(true)
  })
})
