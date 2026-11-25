import { afterEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { reservationsApi } from '@/services/api'
import ReservationDashboardPage from './ReservationDashboardPage.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())

describe('ReservationDashboardPage accessibility', () => {
  it('uses the reservations title as the page heading', async () => {
    vi.spyOn(reservationsApi, 'list').mockResolvedValue([])
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/reservations', component: ReservationDashboardPage },
        { path: '/tables', component: { template: '<div />' } },
      ],
    })
    await router.push('/reservations')
    const wrapper = mount(ReservationDashboardPage, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('My Reservations')
    expect(wrapper.find('h2').exists()).toBe(false)
  })
})
