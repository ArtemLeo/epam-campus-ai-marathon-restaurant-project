import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import EmptyState from './EmptyState.vue'

describe('EmptyState accessibility', () => {
  it('announces its message without exposing the decorative icon', () => {
    const wrapper = mount(EmptyState, {
      props: { icon: '📭', title: 'No reservations', description: 'Try another date.' },
    })
    const status = wrapper.get('[role="status"]')

    expect(status.attributes('aria-live')).toBe('polite')
    expect(status.text()).toContain('No reservations')
    expect(status.text()).toContain('Try another date.')
    expect(wrapper.get('.empty-state__icon').attributes('aria-hidden')).toBe('true')
  })
})
