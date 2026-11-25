import { describe, expect, it } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from './App.vue'

describe('App keyboard navigation', () => {
  it('provides a localized skip link to a focusable main landmark', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/main', component: { template: '<p>Home</p>' } }],
    })
    await router.push('/main')
    const wrapper = shallowMount(App, { global: { plugins: [createPinia(), router] } })

    expect(wrapper.get('.skip-link').attributes('href')).toBe('#main-content')
    expect(wrapper.get('.skip-link').text()).toBe('Skip to main content')
    expect(wrapper.get('main#main-content').attributes('tabindex')).toBe('-1')
    wrapper.unmount()
  })
})
