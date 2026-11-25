import { afterEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { locationsApi } from '@/services/api'
import TablesPage from './TablesPage.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())

describe('TablesPage accessibility', () => {
  it('uses the booking title as the page heading', async () => {
    vi.spyOn(locationsApi, 'list').mockResolvedValue([])
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/tables', component: TablesPage }],
    })
    await router.push('/tables')
    const wrapper = mount(TablesPage, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('Book a Table')
    expect(wrapper.find('h2').exists()).toBe(false)
  })
})
