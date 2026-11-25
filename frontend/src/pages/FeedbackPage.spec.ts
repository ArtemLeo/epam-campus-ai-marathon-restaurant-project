import { afterEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import FeedbackPage from './FeedbackPage.vue'

enableAutoUnmount(afterEach)

describe('FeedbackPage accessibility', () => {
  it('groups feedback type radios under a descriptive legend', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/feedback', component: FeedbackPage }],
    })
    await router.push('/feedback?reservationId=r1')
    const wrapper = mount(FeedbackPage, { global: { plugins: [router] } })

    expect(wrapper.get('fieldset legend').text()).toBe('Feedback type')
    const radios = wrapper.findAll('input[type="radio"]')
    expect(radios).toHaveLength(2)
    expect(radios.every(radio => radio.attributes('name') === 'feedback-type')).toBe(true)
  })
})
