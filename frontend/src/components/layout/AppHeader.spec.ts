import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import AppHeader from './AppHeader.vue'

describe('AppHeader notifications accessibility', () => {
  it('includes the unread count once in the notification button name', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
    })
    const auth = useAuthStore()
    const token = `header.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.signature`
    auth.tokens = { idToken: token, accessToken: token }
    auth.user = { id: 'w1', firstName: 'Olena', lastName: 'Koval', email: 'waiter@example.com', role: 'Waiter' }
    const notifications = useNotificationsStore()
    vi.spyOn(notifications, 'startPolling').mockImplementation(() => undefined)
    notifications.notifications = [{ id: 'n1', message: 'New order', orderId: 'o1', reservationId: null, createdAt: new Date().toISOString(), isRead: false }]

    const wrapper = mount(AppHeader, { global: { plugins: [pinia, router] } })
    const button = wrapper.get('.notifications-btn')
    expect(button.attributes('aria-label')).toContain('1')
    expect(wrapper.get('.badge-dot').attributes('aria-hidden')).toBe('true')
    await button.trigger('click')
    expect(wrapper.get('.notifications-dropdown__header button').attributes('type')).toBe('button')
  })
})
