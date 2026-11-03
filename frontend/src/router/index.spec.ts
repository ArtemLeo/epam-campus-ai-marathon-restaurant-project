import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createDemoTokens, DEMO_USER } from '@/shared/mocks/auth/demo-auth'
import router from './index'

describe('router · group pre-order route', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('scrollTo', vi.fn()) // jsdom has no layout; the router's scrollBehavior calls it
  })

  it('passes :reservationId to the page as a prop', () => {
    const route = router.resolve('/reservations/res-1/group-order')
    expect(route.matched.at(-1)?.props.default).toBe(true)
    expect(route.params.reservationId).toBe('res-1')
    expect(route.meta).toMatchObject({ requireAuth: true, ownsMainLandmark: true })
  })

  it('sends anonymous visitors to /main', async () => {
    await router.push('/reservations/res-1/group-order')
    expect(router.currentRoute.value.fullPath).toBe('/main')
  })

  it('lets a signed-in customer in', async () => {
    localStorage.setItem('auth', JSON.stringify(createDemoTokens()))
    localStorage.setItem('user', JSON.stringify(DEMO_USER))

    await router.push('/reservations/res-1/group-order')

    expect(router.currentRoute.value.fullPath).toBe('/reservations/res-1/group-order')
  })
})
